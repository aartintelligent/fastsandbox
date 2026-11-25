//! Streams of the library as Python async iterators.
//!
//! [`ItemStream`] owns a boxed stream whose items are already Python objects:
//! each stream of `docker-sandbox` (daemon events, creation progress, image
//! pulls, prompts, the output of an interactive session) is mapped once, with
//! its own conversion, then iterated with `async for`. `aclose` drops the
//! stream, which closes its connection to the daemon.

use std::pin::Pin;
use std::sync::Arc;

use futures_util::{Stream, StreamExt};
use pyo3::exceptions::PyStopAsyncIteration;
use pyo3::prelude::*;
use tokio::sync::Mutex;

use crate::error;

/// The boxed stream an [`ItemStream`] iterates.
type Items = Pin<Box<dyn Stream<Item = PyResult<Py<PyAny>>> + Send>>;

/// An async iterator over a stream of the daemon.
///
/// Iterate it with `async for`; call `aclose()` to stop early and close the
/// connection. Items are the serde shape of the library, which the package
/// validates into its models.
#[pyclass(frozen, module = "fastsandbox._native")]
pub(crate) struct ItemStream {
    /// The stream, `None` once closed; the lock serializes the reads.
    inner: Arc<Mutex<Option<Items>>>,
}

impl ItemStream {
    /// Wraps a stream of the library, converting each item with `convert`.
    pub(crate) fn new<S, T, C>(stream: S, convert: C) -> Self
    where
        S: Stream<Item = docker_sandbox::Result<T>> + Send + 'static,
        T: Send + 'static,
        C: Fn(Python<'_>, T) -> PyResult<Py<PyAny>> + Send + Sync + 'static,
    {
        let items = stream.map(move |item| match item {
            Ok(value) => Python::attach(|py| convert(py, value)),
            Err(err) => Err(error::to_py(err)),
        });
        Self::from_items(Box::pin(items))
    }

    /// Wraps a stream whose items are already Python objects.
    pub(crate) fn from_items(items: Items) -> Self {
        Self {
            inner: Arc::new(Mutex::new(Some(items))),
        }
    }
}

impl std::fmt::Debug for ItemStream {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ItemStream").finish_non_exhaustive()
    }
}

#[pymethods]
impl ItemStream {
    /// The iterator itself.
    fn __aiter__(slf: Py<Self>) -> Py<Self> {
        slf
    }

    /// The next item; `StopAsyncIteration` at the end of the stream.
    fn __anext__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let mut guard = inner.lock().await;
            let Some(stream) = guard.as_mut() else {
                return Err(PyStopAsyncIteration::new_err(()));
            };
            if let Some(item) = stream.next().await {
                item
            } else {
                *guard = None;
                Err(PyStopAsyncIteration::new_err(()))
            }
        })
    }

    /// Stops the stream and closes its connection; iterating afterwards ends
    /// at once.
    fn aclose<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            inner.lock().await.take();
            Ok(())
        })
    }
}
