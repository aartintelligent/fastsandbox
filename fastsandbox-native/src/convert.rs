//! Conversions between Rust values and Python objects, and the bridge from
//! the futures of the library to Python awaitables.
//!
//! The serde types of `docker-sandbox` go through `pythonize`, in their serde
//! shape; durations are seconds as floats, byte payloads are `bytes`.

use std::future::Future;
use std::time::Duration;

use bytes::Bytes;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use serde::Serialize;
use serde::de::DeserializeOwned;

use crate::error;

/// A serde value as a Python object.
pub(crate) fn to_py<T: Serialize + ?Sized>(py: Python<'_>, value: &T) -> PyResult<Py<PyAny>> {
    Ok(pythonize::pythonize(py, value)?.unbind())
}

/// A Python object as a serde value of the library.
pub(crate) fn from_py<T: DeserializeOwned>(obj: &Bound<'_, PyAny>) -> PyResult<T> {
    Ok(pythonize::depythonize(obj)?)
}

/// A byte payload as Python `bytes`.
pub(crate) fn to_bytes(py: Python<'_>, data: &[u8]) -> Py<PyAny> {
    PyBytes::new(py, data).into_any().unbind()
}

/// Seconds given by Python as a duration.
///
/// # Errors
///
/// Fails when `seconds` is negative, not finite or too large.
pub(crate) fn duration(seconds: f64) -> PyResult<Duration> {
    Duration::try_from_secs_f64(seconds)
        .map_err(|err| PyValueError::new_err(format!("invalid duration {seconds}: {err}")))
}

/// Optional seconds given by Python as an optional duration.
///
/// # Errors
///
/// Fails as [`duration`] does.
pub(crate) fn optional_duration(seconds: Option<f64>) -> PyResult<Option<Duration>> {
    seconds.map(duration).transpose()
}

/// Copies Python bytes into the payload type of the library.
pub(crate) fn payload(data: &[u8]) -> Bytes {
    Bytes::copy_from_slice(data)
}

/// Runs `fut` on the runtime; the awaitable resolves to its serde value.
pub(crate) fn serde_future<F, T>(py: Python<'_>, fut: F) -> PyResult<Bound<'_, PyAny>>
where
    F: Future<Output = docker_sandbox::Result<T>> + Send + 'static,
    T: Serialize + Send + 'static,
{
    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let value = fut.await.map_err(error::to_py)?;
        Python::attach(|py| to_py(py, &value))
    })
}

/// Runs `fut` on the runtime; the awaitable resolves to `None`.
pub(crate) fn unit_future<F>(py: Python<'_>, fut: F) -> PyResult<Bound<'_, PyAny>>
where
    F: Future<Output = docker_sandbox::Result<()>> + Send + 'static,
{
    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        fut.await.map_err(error::to_py)?;
        Ok(())
    })
}

/// Runs `fut` on the runtime; the awaitable resolves to what `convert` makes
/// of its value, with the interpreter attached.
pub(crate) fn mapped_future<F, T, C>(
    py: Python<'_>,
    fut: F,
    convert: C,
) -> PyResult<Bound<'_, PyAny>>
where
    F: Future<Output = docker_sandbox::Result<T>> + Send + 'static,
    T: Send + 'static,
    C: FnOnce(Python<'_>, T) -> PyResult<Py<PyAny>> + Send + 'static,
{
    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let value = fut.await.map_err(error::to_py)?;
        Python::attach(|py| convert(py, value))
    })
}

/// Runs `fut` on the runtime; the awaitable resolves to the Python class `T`
/// it produces.
pub(crate) fn class_future<F, T>(py: Python<'_>, fut: F) -> PyResult<Bound<'_, PyAny>>
where
    F: Future<Output = docker_sandbox::Result<T>> + Send + 'static,
    T: for<'a> IntoPyObject<'a> + Send + 'static,
{
    pyo3_async_runtimes::tokio::future_into_py(py, async move { fut.await.map_err(error::to_py) })
}
