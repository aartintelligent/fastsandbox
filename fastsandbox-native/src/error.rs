//! Errors of `docker-sandbox` as the exceptions of `fastsandbox.exceptions`.
//!
//! The exception classes are Python, so that they carry typed attributes and
//! documentation and can be caught without importing the extension: this
//! module only classifies an error and calls the matching class with its
//! message and its details as keyword arguments. Every class derives from
//! `fastsandbox.exceptions.SandboxError`.

use docker_sandbox::Error;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// The Python module that defines the exception hierarchy.
const ERRORS_MODULE: &str = "fastsandbox.exceptions";

/// Converts an error of the library into the matching Python exception.
///
/// Attaches to the interpreter on its own, so that it can be called from a
/// future running on the tokio runtime.
#[allow(
    clippy::needless_pass_by_value,
    reason = "the signature of the `map_err` callbacks it is used as"
)]
pub(crate) fn to_py(err: Error) -> PyErr {
    Python::attach(|py| build(py, &err).unwrap_or_else(|failure| failure))
}

/// Builds the exception of `err`, or the error met while building it.
fn build(py: Python<'_>, err: &Error) -> PyResult<PyErr> {
    let details = PyDict::new(py);
    details.set_item("transient", err.is_transient())?;
    let class = classify(err, &details)?;
    let module = py.import(ERRORS_MODULE)?;
    let instance = module
        .getattr(class)?
        .call((err.to_string(),), Some(&details))?;
    Ok(PyErr::from_value(instance))
}

/// The class name for `err`, with its details added to `details`.
fn classify(err: &Error, details: &Bound<'_, PyDict>) -> PyResult<&'static str> {
    let class = match err {
        Error::Api(api) => {
            details.set_item("operation", api.operation())?;
            details.set_item("status", api.status().as_u16())?;
            details.set_item("code", api.code())?;
            details.set_item("detail", api.message())?;
            if err.is_not_found() {
                "NotFoundError"
            } else if err.is_conflict() {
                "ConflictError"
            } else if err.is_invalid_input() {
                "InvalidInputError"
            } else {
                "ApiError"
            }
        }
        Error::Connect { path, .. } => {
            details.set_item("path", path)?;
            "DaemonUnavailableError"
        }
        Error::Http { operation, .. } => {
            details.set_item("operation", *operation)?;
            "DaemonUnavailableError"
        }
        Error::NoSocketPath | Error::Connection(_) => "DaemonUnavailableError",
        Error::Timeout { operation, after } => {
            details.set_item("operation", *operation)?;
            details.set_item("after", after.as_secs_f64())?;
            "SandboxTimeoutError"
        }
        Error::Failed { operation, .. } => {
            details.set_item("operation", *operation)?;
            "OperationFailedError"
        }
        Error::Decode { operation, .. } => {
            details.set_item("operation", *operation)?;
            "ProtocolError"
        }
        Error::UnsupportedVersion { found, supported } => {
            details.set_item("found", found)?;
            details.set_item("supported", supported)?;
            "UnsupportedVersionError"
        }
        Error::InvalidRequest(_) => "InvalidRequestError",
        Error::File { path, .. } => {
            details.set_item("path", path)?;
            "HostFileError"
        }
        Error::Archive { operation, .. } => {
            details.set_item("operation", *operation)?;
            "ArchiveError"
        }
        Error::CommandFailed(output) => {
            details.set_item("exit_code", output.exit_code)?;
            details.set_item("stdout", &output.stdout)?;
            details.set_item("stderr", &output.stderr)?;
            "CommandFailedError"
        }
        Error::Package { path, .. } => {
            details.set_item("path", path)?;
            "KitPackageError"
        }
        Error::Compile(_) => "KitCompileError",
        // A variant added by a newer `docker-sandbox`: still a SandboxError.
        _ => "SandboxError",
    };
    Ok(class)
}

/// The error of a stream or session used after it was closed.
pub(crate) fn closed(what: &str) -> PyErr {
    PyRuntimeError::new_err(format!("the {what} is closed"))
}
