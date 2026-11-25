//! The SSH tunnel of a sandbox, as a Python byte stream.
//!
//! The tunnel is a raw byte stream to the SSH server of the sandbox, which
//! accepts any user, `root` included, without credentials: whoever holds the
//! tunnel is `root` in the sandbox. `proxy_stdio` relays it to the standard
//! input and output of the process, which is what an OpenSSH `ProxyCommand`
//! expects.

use std::sync::Arc;

use docker_sandbox::sandbox::SshTunnel as LibTunnel;
use pyo3::prelude::*;
use tokio::io::{AsyncReadExt, AsyncWriteExt, ReadHalf, WriteHalf};
use tokio::sync::Mutex;

use crate::convert::{payload, to_bytes};
use crate::error;

/// A byte tunnel to the SSH server of a sandbox.
#[pyclass(frozen, module = "fastsandbox._native")]
pub(crate) struct SshTunnel {
    /// The reading half, `None` once closed.
    reader: Arc<Mutex<Option<ReadHalf<LibTunnel>>>>,
    /// The writing half, `None` once closed.
    writer: Arc<Mutex<Option<WriteHalf<LibTunnel>>>>,
}

impl std::fmt::Debug for SshTunnel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SshTunnel").finish_non_exhaustive()
    }
}

impl SshTunnel {
    /// Wraps a tunnel of the library.
    pub(crate) fn new(tunnel: LibTunnel) -> Self {
        let (reader, writer) = tokio::io::split(tunnel);
        Self {
            reader: Arc::new(Mutex::new(Some(reader))),
            writer: Arc::new(Mutex::new(Some(writer))),
        }
    }
}

#[pymethods]
impl SshTunnel {
    /// Reads at most `size` bytes; an empty result is the end of the stream.
    #[pyo3(signature = (size=65536))]
    fn read<'py>(&self, py: Python<'py>, size: usize) -> PyResult<Bound<'py, PyAny>> {
        let reader = Arc::clone(&self.reader);
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let mut reader = reader.lock().await;
            let reader = reader.as_mut().ok_or_else(|| error::closed("tunnel"))?;
            let mut buffer = vec![0; size.max(1)];
            let read = reader.read(&mut buffer).await?;
            buffer.truncate(read);
            Python::attach(|py| Ok(to_bytes(py, &buffer)))
        })
    }

    /// Writes `data` to the tunnel.
    fn write<'py>(&self, py: Python<'py>, data: &[u8]) -> PyResult<Bound<'py, PyAny>> {
        let writer = Arc::clone(&self.writer);
        let data = payload(data);
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let mut writer = writer.lock().await;
            let writer = writer.as_mut().ok_or_else(|| error::closed("tunnel"))?;
            writer.write_all(&data).await?;
            writer.flush().await?;
            Ok(())
        })
    }

    /// Closes the tunnel.
    fn close<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let reader = Arc::clone(&self.reader);
        let writer = Arc::clone(&self.writer);
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            if let Some(mut writer) = writer.lock().await.take() {
                writer.shutdown().await?;
            }
            reader.lock().await.take();
            Ok(())
        })
    }

    /// Relays the tunnel to the standard input and output of the process
    /// until either side ends: the job of an OpenSSH `ProxyCommand`.
    fn proxy_stdio<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let reader = Arc::clone(&self.reader);
        let writer = Arc::clone(&self.writer);
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let mut reader = reader
                .lock()
                .await
                .take()
                .ok_or_else(|| error::closed("tunnel"))?;
            let mut writer = writer
                .lock()
                .await
                .take()
                .ok_or_else(|| error::closed("tunnel"))?;
            let to_sandbox = async {
                tokio::io::copy(&mut tokio::io::stdin(), &mut writer).await?;
                writer.shutdown().await
            };
            let from_sandbox = async {
                let mut stdout = tokio::io::stdout();
                tokio::io::copy(&mut reader, &mut stdout).await?;
                stdout.flush().await
            };
            tokio::try_join!(to_sandbox, from_sandbox)?;
            Ok(())
        })
    }
}
