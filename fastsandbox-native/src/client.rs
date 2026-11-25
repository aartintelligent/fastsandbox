//! The client of the daemon and the handles of its domains: daemon, sandbox
//! collection, images, events, network policy, MCP and prompts.
//!
//! Each class owns a clone of the handle of `docker-sandbox`, which shares
//! the connection settings of the client; clones are cheap.

use std::path::PathBuf;

use docker_sandbox::VersionPolicy;
use docker_sandbox::mcp::McpServerCheck;
use docker_sandbox::policy::{NetworkCheck, RuleChange};
use docker_sandbox::sandbox::{CreateEvent, CreateRequest};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde_json::Value;

use crate::convert::{
    from_py, optional_duration, payload, serde_future, to_bytes, to_py, unit_future,
};
use crate::sandbox::Sandbox;
use crate::stream::ItemStream;

/// Connects to the daemon with the given settings (see `connect`).
pub(crate) fn connect<'py>(
    py: Python<'py>,
    socket: Option<PathBuf>,
    timeout: Option<f64>,
    long_operation_timeout: Option<f64>,
    version_policy: Option<&str>,
) -> PyResult<Bound<'py, PyAny>> {
    let mut builder = docker_sandbox::Client::builder();
    if let Some(socket) = socket {
        builder = builder.with_socket(socket);
    }
    if let Some(timeout) = optional_duration(timeout)? {
        builder = builder.with_timeout(timeout);
    }
    if let Some(timeout) = optional_duration(long_operation_timeout)? {
        builder = builder.with_long_operation_timeout(timeout);
    }
    if let Some(policy) = version_policy {
        builder = builder.with_version_policy(parse_version_policy(policy)?);
    }
    crate::convert::class_future(py, async move {
        builder.connect().await.map(|inner| Client { inner })
    })
}

/// The version policy named by Python.
fn parse_version_policy(name: &str) -> PyResult<VersionPolicy> {
    match name {
        "strict" => Ok(VersionPolicy::Strict),
        "warn" => Ok(VersionPolicy::Warn),
        "ignore" => Ok(VersionPolicy::Ignore),
        other => Err(PyValueError::new_err(format!(
            "unknown version policy {other:?}: expected \"strict\", \"warn\" or \"ignore\""
        ))),
    }
}

/// A connection to the daemon: the entry point of every other handle.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct Client {
    /// The client of the library.
    pub(crate) inner: docker_sandbox::Client,
}

#[pymethods]
impl Client {
    /// The socket the client talks to.
    #[getter]
    fn socket_path(&self) -> PathBuf {
        self.inner.socket_path().to_path_buf()
    }

    /// The health the daemon reported when the client connected.
    #[getter]
    fn health(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        to_py(py, self.inner.health())
    }

    /// The daemon itself: health, settings, log levels, disk usage.
    fn daemon(&self) -> Daemon {
        Daemon {
            inner: self.inner.daemon(),
        }
    }

    /// The collection of sandboxes: list, look up, create.
    fn sandboxes(&self) -> Sandboxes {
        Sandboxes {
            inner: self.inner.sandboxes(),
        }
    }

    /// The handle of the sandbox named `name`; nothing is checked until it
    /// is used.
    fn sandbox(&self, name: String) -> Sandbox {
        Sandbox::new(self.inner.sandbox(name))
    }

    /// The images of the daemon.
    fn images(&self) -> Images {
        Images {
            inner: self.inner.images(),
        }
    }

    /// The event stream of the daemon.
    fn events(&self) -> Events {
        Events {
            inner: self.inner.events(),
        }
    }

    /// The network policy.
    fn policy(&self) -> Policy {
        Policy {
            inner: self.inner.policy(),
        }
    }

    /// The MCP gateway settings.
    fn mcp(&self) -> Mcp {
        Mcp {
            inner: self.inner.mcp(),
        }
    }

    /// The approval prompts of the daemon.
    fn prompts(&self) -> Prompts {
        Prompts {
            inner: self.inner.prompts(),
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "Client(socket_path={:?})",
            self.inner.socket_path().display().to_string()
        )
    }
}

/// The daemon: health, information, settings, log levels and disk usage.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct Daemon {
    /// The handle of the library.
    inner: docker_sandbox::daemon::Daemon,
}

#[pymethods]
impl Daemon {
    /// The current health of the daemon.
    fn health<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.health().await })
    }

    /// Version and build information.
    fn info<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.info().await })
    }

    /// Every setting with its value.
    fn settings<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.settings().await })
    }

    /// The setting `key`.
    fn setting<'py>(&self, py: Python<'py>, key: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.setting(&key).await })
    }

    /// Sets `key` to `value`, any JSON value.
    fn set_setting<'py>(
        &self,
        py: Python<'py>,
        key: String,
        value: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let value: Value = from_py(value)?;
        let inner = self.inner.clone();
        serde_future(py, async move { inner.set_setting(&key, value).await })
    }

    /// Resets `key` to its default.
    fn unset_setting<'py>(&self, py: Python<'py>, key: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.unset_setting(&key).await })
    }

    /// The log level of every target.
    fn log_levels<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.log_levels().await })
    }

    /// Sets the log level of `target`.
    fn set_log_level<'py>(
        &self,
        py: Python<'py>,
        target: String,
        level: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(
            py,
            async move { inner.set_log_level(&target, &level).await },
        )
    }

    /// Disk usage of images, containers and volumes.
    fn disk_usage<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.disk_usage().await })
    }

    /// The internal state the daemon reports for debugging.
    fn debug_state<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.debug_state().await })
    }

    /// The diagnostics the daemon collects.
    fn diagnostics<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.diagnostics().await })
    }
}

/// The collection of sandboxes.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct Sandboxes {
    /// The handle of the library.
    inner: docker_sandbox::sandbox::Sandboxes,
}

#[pymethods]
impl Sandboxes {
    /// Every sandbox.
    fn list<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.list().await })
    }

    /// The sandbox `name`; `NotFoundError` when there is none.
    fn get<'py>(&self, py: Python<'py>, name: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.get(&name).await })
    }

    /// The sandbox `name`, or `None`.
    fn find<'py>(&self, py: Python<'py>, name: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.find(&name).await })
    }

    /// Creates a sandbox from a creation request and waits for the result.
    fn create<'py>(
        &self,
        py: Python<'py>,
        request: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let request: CreateRequest = from_py(request)?;
        let inner = self.inner.clone();
        serde_future(py, async move { inner.create(&request).await })
    }

    /// Creates a sandbox, streaming its progress: items are
    /// `{"type": "progress" | "result" | "error" | "unknown", ...}`.
    fn create_stream<'py>(
        &self,
        py: Python<'py>,
        request: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let request: CreateRequest = from_py(request)?;
        let inner = self.inner.clone();
        crate::convert::class_future(py, async move {
            inner
                .create_stream(&request)
                .await
                .map(|stream| ItemStream::new(stream, create_event))
        })
    }
}

/// A creation event as a tagged dictionary.
fn create_event(py: Python<'_>, event: CreateEvent) -> PyResult<Py<PyAny>> {
    let item = PyDict::new(py);
    match event {
        CreateEvent::Progress(message) => {
            item.set_item("type", "progress")?;
            item.set_item("message", message)?;
        }
        CreateEvent::Result(created) => {
            item.set_item("type", "result")?;
            item.set_item("created", to_py(py, &*created)?)?;
        }
        CreateEvent::Error(message) => {
            item.set_item("type", "error")?;
            item.set_item("message", message)?;
        }
        CreateEvent::Unknown(raw) => {
            item.set_item("type", "unknown")?;
            item.set_item("raw", to_py(py, &raw)?)?;
        }
        other => {
            item.set_item("type", "unknown")?;
            item.set_item("raw", format!("{other:?}"))?;
        }
    }
    Ok(item.into_any().unbind())
}

/// The images of the daemon.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct Images {
    /// The handle of the library.
    inner: docker_sandbox::image::Images,
}

#[pymethods]
impl Images {
    /// Every image, untagged ones included.
    fn list<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.list().await })
    }

    /// The details of `reference`.
    fn inspect<'py>(&self, py: Python<'py>, reference: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.inspect(&reference).await })
    }

    /// Whether `reference` is present.
    fn exists<'py>(&self, py: Python<'py>, reference: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.exists(&reference).await })
    }

    /// The local metadata of `reference`.
    fn local_metadata<'py>(
        &self,
        py: Python<'py>,
        reference: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.local_metadata(&reference).await })
    }

    /// Pulls `reference` and waits for the end of the pull.
    fn pull<'py>(&self, py: Python<'py>, reference: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.pull(&reference).await })
    }

    /// Pulls `reference`, streaming its progress.
    fn pull_stream<'py>(&self, py: Python<'py>, reference: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        crate::convert::class_future(py, async move {
            inner
                .pull_stream(&reference)
                .await
                .map(|stream| ItemStream::new(stream, |py, item| to_py(py, &item)))
        })
    }

    /// Loads an image archive (`docker save` format).
    fn load<'py>(&self, py: Python<'py>, archive: &[u8]) -> PyResult<Bound<'py, PyAny>> {
        let archive = payload(archive);
        let inner = self.inner.clone();
        unit_future(py, async move { inner.load(archive).await })
    }

    /// Loads an image archive from a file of the host.
    fn load_file<'py>(&self, py: Python<'py>, path: PathBuf) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.load_file(&path).await })
    }

    /// Exports `reference` as an image archive.
    fn export<'py>(&self, py: Python<'py>, reference: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        crate::convert::mapped_future(
            py,
            async move { inner.export(&reference).await },
            |py, data| Ok(to_bytes(py, &data)),
        )
    }

    /// Removes `reference`.
    fn remove<'py>(&self, py: Python<'py>, reference: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.remove(&reference).await })
    }
}

/// The event stream of the daemon.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct Events {
    /// The handle of the library.
    inner: docker_sandbox::event::Events,
}

#[pymethods]
impl Events {
    /// Every event: the current state replayed, a `sync` event, then the
    /// live events.
    fn subscribe<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        crate::convert::class_future(py, async move {
            inner
                .subscribe()
                .await
                .map(|stream| ItemStream::new(stream, |py, event| to_py(py, &event)))
        })
    }

    /// The live events only, after the `sync` event.
    fn subscribe_live<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        crate::convert::class_future(py, async move {
            inner
                .subscribe_live()
                .await
                .map(|stream| ItemStream::new(stream, |py, event| to_py(py, &event)))
        })
    }
}

/// The network policy of the daemon.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct Policy {
    /// The handle of the library.
    inner: docker_sandbox::policy::Policy,
}

#[pymethods]
impl Policy {
    /// Every network rule.
    fn rules<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.rules().await })
    }

    /// Applies rule changes; each result says whether it applied.
    fn apply<'py>(
        &self,
        py: Python<'py>,
        changes: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let changes: Vec<RuleChange> = from_py(changes)?;
        let inner = self.inner.clone();
        serde_future(py, async move { inner.apply(&changes).await })
    }

    /// Applies rule changes and fails on the first one that did not apply.
    fn apply_all<'py>(
        &self,
        py: Python<'py>,
        changes: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let changes: Vec<RuleChange> = from_py(changes)?;
        let inner = self.inner.clone();
        serde_future(py, async move { inner.apply_all(&changes).await })
    }

    /// Removes the rule `id`.
    fn remove_rule<'py>(&self, py: Python<'py>, id: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.remove_rule(&id).await })
    }

    /// What the policy decides for a host or an HTTP request.
    fn check<'py>(
        &self,
        py: Python<'py>,
        check: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let check: NetworkCheck = from_py(check)?;
        let inner = self.inner.clone();
        serde_future(py, async move { inner.check(&check).await })
    }

    /// The hosts sandboxes reached or were refused.
    fn log<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.log().await })
    }

    /// The governance profiles.
    fn profiles<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.profiles().await })
    }

    /// Whether the policy still needs its initial setup.
    fn setup_needed<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.setup_needed().await })
    }

    /// Reloads the policy.
    fn refresh<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.refresh().await })
    }
}

/// The MCP gateway settings of the daemon.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct Mcp {
    /// The handle of the library.
    inner: docker_sandbox::mcp::Mcp,
}

#[pymethods]
impl Mcp {
    /// How the gateway runs MCP servers.
    fn gateway_mode<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.gateway_mode().await })
    }

    /// Whether an MCP server definition can be registered.
    fn check_registration<'py>(
        &self,
        py: Python<'py>,
        server: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let server: McpServerCheck = from_py(server)?;
        let inner = self.inner.clone();
        serde_future(py, async move { inner.check_registration(&server).await })
    }
}

/// The approval prompts of the daemon.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct Prompts {
    /// The handle of the library.
    inner: docker_sandbox::prompt::Prompts,
}

#[pymethods]
impl Prompts {
    /// The stream of prompts: the pending ones, then the new ones.
    fn subscribe<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        crate::convert::class_future(py, async move {
            inner
                .subscribe()
                .await
                .map(|stream| ItemStream::new(stream, |py, item| to_py(py, &item)))
        })
    }

    /// Answers the prompt `id` with the option `option_id`.
    fn respond<'py>(
        &self,
        py: Python<'py>,
        id: String,
        option_id: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.respond(&id, &option_id).await })
    }
}
