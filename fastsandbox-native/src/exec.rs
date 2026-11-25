//! Interactive sessions and the session guard, as Python objects.
//!
//! An [`ExecSession`] is either collected whole (`collect`, which writes the
//! standard input then reads everything until the exit) or used piece by
//! piece: the first `write`, `close_stdin` or read splits it into its input,
//! its output stream and its control, which then live on their own; it cannot
//! be collected afterwards.
//!
//! A [`SessionGuard`] keeps its sandbox running until it is released or
//! dropped; the package exposes it as an async context manager.

use std::sync::{Arc, Mutex, PoisonError};
use std::time::Duration;

use docker_sandbox::exec::{
    ExecControl, ExecInput, ExecOutputStream, OutputChunk, OutputStream, TerminalSize,
};

use pyo3::exceptions::{PyRuntimeError, PyStopAsyncIteration};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use tokio::io::AsyncWriteExt;

use crate::convert::{duration, payload, serde_future, to_bytes};
use crate::error;

/// The parts of a session once it is split.
struct Parts {
    /// The standard input, `None` once closed.
    input: tokio::sync::Mutex<Option<ExecInput>>,
    /// The output, `None` once it ended.
    output: tokio::sync::Mutex<Option<ExecOutputStream>>,
}

/// An interactive command or agent session.
///
/// Send its standard input with `write` and `close_stdin`, read its output
/// with `async for chunk in session` (dictionaries `{"stream": "stdout" |
/// "stderr", "data": bytes}`), resize its terminal, wait for its exit code;
/// or `collect` it whole.
#[pyclass(frozen, module = "fastsandbox._native")]
pub(crate) struct ExecSession {
    /// The id of the execution.
    id: String,
    /// Resize, inspect and wait; usable before and after the split.
    control: ExecControl,
    /// The session, until it is split or collected.
    whole: Mutex<Option<docker_sandbox::exec::ExecSession>>,
    /// The parts, once split.
    parts: Arc<std::sync::OnceLock<Arc<Parts>>>,
}

impl std::fmt::Debug for ExecSession {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ExecSession")
            .field("id", &self.id)
            .finish_non_exhaustive()
    }
}

impl ExecSession {
    /// Wraps a session of the library.
    pub(crate) fn new(session: docker_sandbox::exec::ExecSession) -> Self {
        Self {
            id: session.id().to_owned(),
            control: session.control(),
            whole: Mutex::new(Some(session)),
            parts: Arc::new(std::sync::OnceLock::new()),
        }
    }

    /// The parts of the session, splitting it on first use.
    fn parts(&self) -> PyResult<Arc<Parts>> {
        if let Some(parts) = self.parts.get() {
            return Ok(Arc::clone(parts));
        }
        let session = self
            .whole
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .take();
        match session {
            Some(session) => {
                let (input, output, _control) = session.split();
                let parts = Arc::new(Parts {
                    input: tokio::sync::Mutex::new(Some(input)),
                    output: tokio::sync::Mutex::new(Some(output)),
                });
                Ok(Arc::clone(self.parts.get_or_init(|| parts)))
            }
            // Split concurrently by another call, or collected.
            None => self
                .parts
                .get()
                .map(Arc::clone)
                .ok_or_else(|| PyRuntimeError::new_err("the session was collected")),
        }
    }
}

/// An output chunk as a dictionary.
fn chunk(py: Python<'_>, chunk: &OutputChunk) -> PyResult<Py<PyAny>> {
    let item = PyDict::new(py);
    let stream = match chunk.stream {
        OutputStream::Stdout => "stdout",
        OutputStream::Stderr => "stderr",
        #[allow(
            unreachable_patterns,
            reason = "the enum is non-exhaustive in newer releases"
        )]
        _ => "other",
    };
    item.set_item("stream", stream)?;
    item.set_item("data", to_bytes(py, &chunk.data))?;
    Ok(item.into_any().unbind())
}

#[pymethods]
impl ExecSession {
    /// The id of the execution.
    #[getter]
    fn id(&self) -> &str {
        &self.id
    }

    fn __repr__(&self) -> String {
        format!("ExecSession(id={:?})", self.id)
    }

    /// Writes `data` to the standard input.
    fn write<'py>(&self, py: Python<'py>, data: &[u8]) -> PyResult<Bound<'py, PyAny>> {
        let parts = self.parts()?;
        let data = payload(data);
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let mut input = parts.input.lock().await;
            let input = input
                .as_mut()
                .ok_or_else(|| error::closed("standard input"))?;
            input.write_all(&data).await?;
            input.flush().await?;
            Ok(())
        })
    }

    /// Closes the standard input: the command reads end of file.
    fn close_stdin<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let parts = self.parts()?;
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let input = parts.input.lock().await.take();
            if let Some(mut input) = input {
                input.shutdown().await?;
            }
            Ok(())
        })
    }

    /// The session itself, iterated for its output.
    fn __aiter__(slf: Py<Self>) -> Py<Self> {
        slf
    }

    /// The next output chunk; `StopAsyncIteration` when the output ends.
    fn __anext__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let parts = self.parts()?;
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let mut output = parts.output.lock().await;
            let Some(stream) = output.as_mut() else {
                return Err(PyStopAsyncIteration::new_err(()));
            };
            match stream.next().await {
                Some(Ok(item)) => Python::attach(|py| chunk(py, &item)),
                Some(Err(err)) => Err(error::to_py(err)),
                None => {
                    *output = None;
                    Err(PyStopAsyncIteration::new_err(()))
                }
            }
        })
    }

    /// Resizes the terminal of a TTY session.
    fn resize<'py>(&self, py: Python<'py>, width: u16, height: u16) -> PyResult<Bound<'py, PyAny>> {
        let control = self.control.clone();
        crate::convert::unit_future(py, async move {
            control.resize(TerminalSize { height, width }).await
        })
    }

    /// The state of the execution.
    fn inspect<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let control = self.control.clone();
        serde_future(py, async move { control.inspect().await })
    }

    /// Waits for the exit code, for at most `timeout` seconds.
    #[pyo3(signature = (timeout=60.0))]
    fn wait<'py>(&self, py: Python<'py>, timeout: f64) -> PyResult<Bound<'py, PyAny>> {
        let timeout = duration(timeout)?;
        let control = self.control.clone();
        serde_future(py, async move { control.wait(timeout).await })
    }

    /// Writes `stdin`, closes it, reads every output until the exit and
    /// returns `{"exit_code", "stdout", "stderr"}` (bytes); waits at most
    /// `exit_timeout` seconds for the exit code once the output ended.
    #[pyo3(signature = (stdin=None, exit_timeout=10.0))]
    fn collect<'py>(
        &self,
        py: Python<'py>,
        stdin: Option<&[u8]>,
        exit_timeout: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let exit_timeout: Duration = duration(exit_timeout)?;
        let stdin = payload(stdin.unwrap_or_default());
        let session = self
            .whole
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .take()
            .ok_or_else(|| PyRuntimeError::new_err("the session is already in use or collected"))?;
        crate::convert::mapped_future(
            py,
            async move { session.collect(stdin, exit_timeout).await },
            |py, output| {
                let item = PyDict::new(py);
                item.set_item("exit_code", output.exit_code)?;
                item.set_item("stdout", to_bytes(py, &output.stdout))?;
                item.set_item("stderr", to_bytes(py, &output.stderr))?;
                Ok(item.into_any().unbind())
            },
        )
    }
}

/// Keeps a sandbox running while held.
///
/// The sandbox stops about 30 s after the last guard is released. `release`
/// closes the session at once; a guard dropped by the garbage collector
/// closes it too, later.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug)]
pub(crate) struct SessionGuard {
    /// The name of the sandbox.
    sandbox: String,
    /// The guard of the library, `None` once released.
    inner: Mutex<Option<docker_sandbox::sandbox::SessionGuard>>,
}

impl SessionGuard {
    /// Wraps a guard of the library.
    pub(crate) fn new(guard: docker_sandbox::sandbox::SessionGuard) -> Self {
        Self {
            sandbox: guard.sandbox().to_owned(),
            inner: Mutex::new(Some(guard)),
        }
    }

    /// The guard, locked.
    fn guard(&self) -> std::sync::MutexGuard<'_, Option<docker_sandbox::sandbox::SessionGuard>> {
        self.inner.lock().unwrap_or_else(PoisonError::into_inner)
    }
}

#[pymethods]
impl SessionGuard {
    /// The name of the sandbox the session keeps running.
    #[getter]
    fn sandbox(&self) -> &str {
        &self.sandbox
    }

    /// Whether the session is still open.
    #[getter]
    fn is_connected(&self) -> bool {
        self.guard()
            .as_ref()
            .is_some_and(docker_sandbox::sandbox::SessionGuard::is_connected)
    }

    /// Whether the guard was released.
    #[getter]
    fn released(&self) -> bool {
        self.guard().is_none()
    }

    /// Closes the session; the sandbox stops about 30 s later if nothing
    /// else holds it.
    fn release(&self) {
        let guard = self.guard().take();
        drop(guard);
    }

    fn __repr__(&self) -> String {
        format!(
            "SessionGuard(sandbox={:?}, released={})",
            self.sandbox,
            self.released()
        )
    }
}
