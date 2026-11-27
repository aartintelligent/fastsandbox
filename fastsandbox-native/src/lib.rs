//! The native extension of `fastsandbox`: `docker-sandbox`, bridged to Python.
//!
//! Every handle of the library (`Client`, `Sandbox`, `Images`, …) becomes a
//! frozen Python class owning a clone of it; every async method returns an
//! awaitable whose future runs on the shared tokio runtime of
//! `pyo3-async-runtimes`, so that the library always finds the reactor it
//! needs, and whose cancellation from Python drops the Rust future.
//!
//! Payloads cross the boundary in the serde shape of the library — the shape
//! of the daemon API — as plain Python objects; the Pydantic models of
//! `fastsandbox.models` validate them. Errors become the exception hierarchy
//! of `fastsandbox.exceptions`. This module is private: the package wraps it.

mod client;
mod convert;
mod error;
mod exec;
mod kit;
mod sandbox;
mod ssh;
mod stream;

use pyo3::prelude::*;

/// The `fastsandbox._native` module.
#[pymodule]
mod _native {
    use std::path::PathBuf;

    use pyo3::prelude::*;

    #[pymodule_export]
    use crate::client::{Client, Daemon, Events, Images, Mcp, Policy, Prompts, Sandboxes};
    #[pymodule_export]
    use crate::exec::{ExecSession, SessionGuard};
    #[pymodule_export]
    use crate::kit::{KitAgent, KitCompiler, KitForge, KitPackage};
    #[pymodule_export]
    use crate::sandbox::Sandbox;
    #[pymodule_export]
    use crate::ssh::SshTunnel;
    #[pymodule_export]
    use crate::stream::ItemStream;

    /// Connects to the daemon, checks its health and its API version.
    ///
    /// `socket` overrides the socket path, otherwise taken from
    /// `DOCKER_SANDBOXES_API`, then from the state directory of `sbx`.
    /// `timeout` bounds ordinary requests and `long_operation_timeout` the
    /// long ones (creation, image pulls), in seconds. `version_policy` is
    /// `"strict"` (the default), `"warn"` or `"ignore"`: what to do when the
    /// daemon reports an API version this release has not been audited on.
    #[pyfunction]
    #[pyo3(signature = (socket=None, timeout=None, long_operation_timeout=None, version_policy=None))]
    fn connect<'py>(
        py: Python<'py>,
        socket: Option<PathBuf>,
        timeout: Option<f64>,
        long_operation_timeout: Option<f64>,
        version_policy: Option<&str>,
    ) -> PyResult<Bound<'py, PyAny>> {
        crate::client::connect(py, socket, timeout, long_operation_timeout, version_policy)
    }

    /// The socket path the daemon is reached at by default, if one can be
    /// found: `DOCKER_SANDBOXES_API`, then the state directory of `sbx`.
    #[pyfunction]
    fn default_socket_path() -> Option<PathBuf> {
        docker_sandbox::default_socket_path()
    }

    /// Adds the constants of the module.
    #[pymodule_init]
    fn init(module: &Bound<'_, PyModule>) -> PyResult<()> {
        let supported = docker_sandbox::SUPPORTED_API;
        module.add("__version__", env!("CARGO_PKG_VERSION"))?;
        module.add("SOCKET_ENV", docker_sandbox::SOCKET_ENV)?;
        module.add(
            "SUPPORTED_API",
            (
                supported.min.to_string(),
                supported.max_exclusive.to_string(),
            ),
        )?;
        Ok(())
    }
}
