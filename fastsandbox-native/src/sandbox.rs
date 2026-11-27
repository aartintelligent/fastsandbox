//! The handle of one sandbox: life cycle, sessions, files, ports, network
//! rules, credentials, kits, MCP servers, command execution and SSH.
//!
//! The methods mirror those `docker-sandbox` spreads over its domain modules
//! (`exec`, `policy`, `mcp`, …) in one class, as the library does on its own
//! `Sandbox` type.

use std::path::PathBuf;

use docker_sandbox::exec::{AgentSessionSpec, AttachSpec, ExecSpec};
use docker_sandbox::sandbox::{
    CredentialsUpdate, DeleteOptions, PortBinding, StartOptions, SwapRequest,
};
use pyo3::prelude::*;
use serde_json::Value;

use crate::convert::{
    class_future, from_py, mapped_future, optional_duration, payload, serde_future, to_bytes,
    unit_future,
};
use crate::exec::{ExecSession, SessionGuard};
use crate::ssh::SshTunnel;

/// A sandbox of the daemon, by name.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct Sandbox {
    /// The handle of the library.
    pub(crate) inner: docker_sandbox::sandbox::Sandbox,
}

impl Sandbox {
    /// Wraps a handle of the library.
    pub(crate) fn new(inner: docker_sandbox::sandbox::Sandbox) -> Self {
        Self { inner }
    }
}

#[pymethods]
impl Sandbox {
    /// The name of the sandbox.
    #[getter]
    fn name(&self) -> String {
        self.inner.name().to_owned()
    }

    fn __repr__(&self) -> String {
        format!("Sandbox(name={:?})", self.inner.name())
    }

    // Life cycle.

    /// The current state of the sandbox.
    fn inspect<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.inspect().await })
    }

    /// Whether the sandbox exists.
    fn exists<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.exists().await })
    }

    /// Starts the sandbox (idempotent); it stops again about 30 s after the
    /// last session closes, see `hold_session`.
    #[pyo3(signature = (ssh_agent_socket=None))]
    fn start<'py>(
        &self,
        py: Python<'py>,
        ssh_agent_socket: Option<String>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move {
            match ssh_agent_socket {
                Some(path) => {
                    let options = StartOptions::default().with_ssh_agent_socket(path);
                    inner.start_with(&options).await
                }
                None => inner.start().await,
            }
        })
    }

    /// Stops the sandbox.
    fn stop<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.stop().await })
    }

    /// Deletes the sandbox; `force` stops it first, `expected_id` refuses to
    /// delete a different sandbox that took the same name.
    #[pyo3(signature = (force=false, expected_id=None))]
    fn delete<'py>(
        &self,
        py: Python<'py>,
        force: bool,
        expected_id: Option<String>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let mut options = DeleteOptions::default();
        if force {
            options = options.forced();
        }
        if let Some(id) = expected_id {
            options = options.with_expected_id(id);
        }
        let inner = self.inner.clone();
        unit_future(py, async move { inner.delete_with(&options).await })
    }

    /// Saves the sandbox as the image `tag`, a template for new sandboxes.
    fn save<'py>(&self, py: Python<'py>, tag: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.save(&tag).await })
    }

    /// Sets the working directory of new sessions.
    fn set_working_dir<'py>(&self, py: Python<'py>, dir: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.set_working_dir(&dir).await })
    }

    /// Grants the sandbox access to an existing path of the host.
    fn allow_host_path<'py>(
        &self,
        py: Python<'py>,
        host_path: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.allow_host_path(&host_path).await })
    }

    /// Revokes access to a path of the host.
    fn revoke_host_path<'py>(
        &self,
        py: Python<'py>,
        host_path: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.revoke_host_path(&host_path).await })
    }

    /// The metrics of the virtual machine, in Prometheus text format.
    fn vm_metrics<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.vm_metrics().await })
    }

    // Sessions.

    /// Opens a session that keeps the sandbox running while it is held.
    fn hold_session<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        class_future(py, async move {
            inner.hold_session().await.map(SessionGuard::new)
        })
    }

    /// Starts the sandbox if needed and holds a session on it.
    fn ensure_running<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        class_future(py, async move {
            inner.ensure_running().await.map(SessionGuard::new)
        })
    }

    // Commands.

    /// Runs a command to completion; `timeout` (seconds) bounds it.
    #[pyo3(signature = (spec, timeout=None))]
    fn exec<'py>(
        &self,
        py: Python<'py>,
        spec: &Bound<'py, PyAny>,
        timeout: Option<f64>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let mut spec: ExecSpec = from_py(spec)?;
        if let Some(timeout) = optional_duration(timeout)? {
            spec = spec.with_timeout(timeout);
        }
        let inner = self.inner.clone();
        serde_future(py, async move { inner.exec(&spec).await })
    }

    /// The state of the execution `exec_id`, while the daemon remembers it.
    fn exec_inspect<'py>(&self, py: Python<'py>, exec_id: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.exec_inspect(&exec_id).await })
    }

    /// Starts an interactive command: standard input, output streams, size
    /// of the terminal and exit code through the session.
    fn attach<'py>(
        &self,
        py: Python<'py>,
        spec: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let spec: AttachSpec = from_py(spec)?;
        let inner = self.inner.clone();
        class_future(py, async move {
            inner.attach(&spec).await.map(ExecSession::new)
        })
    }

    /// Starts the agent of the sandbox in an interactive session.
    fn agent_session<'py>(
        &self,
        py: Python<'py>,
        spec: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let spec: AgentSessionSpec = from_py(spec)?;
        let inner = self.inner.clone();
        class_future(py, async move {
            inner.agent_session(&spec).await.map(ExecSession::new)
        })
    }

    // Files.

    /// Extracts a tar archive into `dir` of the sandbox.
    fn upload_archive<'py>(
        &self,
        py: Python<'py>,
        dir: String,
        archive: &[u8],
    ) -> PyResult<Bound<'py, PyAny>> {
        let archive = payload(archive);
        let inner = self.inner.clone();
        unit_future(py, async move { inner.upload_archive(&dir, archive).await })
    }

    /// A tar archive of `path` of the sandbox.
    fn download_archive<'py>(&self, py: Python<'py>, path: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        mapped_future(
            py,
            async move { inner.download_archive(&path).await },
            |py, data| Ok(to_bytes(py, &data)),
        )
    }

    /// Writes `contents` to the file `path`, with the permission bits `mode`.
    #[pyo3(signature = (path, contents, mode=None))]
    fn write_file<'py>(
        &self,
        py: Python<'py>,
        path: String,
        contents: &[u8],
        mode: Option<u32>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let contents = payload(contents);
        let inner = self.inner.clone();
        unit_future(py, async move {
            match mode {
                Some(mode) => inner.write_file_with_mode(&path, contents, mode).await,
                None => inner.write_file(&path, contents).await,
            }
        })
    }

    /// The contents of the file `path`.
    fn read_file<'py>(&self, py: Python<'py>, path: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        mapped_future(
            py,
            async move { inner.read_file(&path).await },
            |py, data| Ok(to_bytes(py, &data)),
        )
    }

    /// Copies the directory `host_dir` of the host into `dir` of the sandbox.
    fn upload_dir<'py>(
        &self,
        py: Python<'py>,
        host_dir: PathBuf,
        dir: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.upload_dir(&host_dir, &dir).await })
    }

    /// Copies `path` of the sandbox into the directory `host_dir` of the host.
    fn download_dir<'py>(
        &self,
        py: Python<'py>,
        path: String,
        host_dir: PathBuf,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(
            py,
            async move { inner.download_dir(&path, &host_dir).await },
        )
    }

    // Ports.

    /// The published ports.
    fn ports<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.ports().await })
    }

    /// Publishes ports; the result has the host ports the daemon assigned.
    fn publish<'py>(
        &self,
        py: Python<'py>,
        ports: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let ports: Vec<PortBinding> = from_py(ports)?;
        let inner = self.inner.clone();
        serde_future(py, async move { inner.publish(&ports).await })
    }

    /// Unpublishes ports.
    fn unpublish<'py>(
        &self,
        py: Python<'py>,
        ports: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let ports: Vec<PortBinding> = from_py(ports)?;
        let inner = self.inner.clone();
        unit_future(py, async move { inner.unpublish(&ports).await })
    }

    /// Replaces a port the sandbox publishes when it starts.
    fn replace_desired_port<'py>(
        &self,
        py: Python<'py>,
        old: &Bound<'py, PyAny>,
        new: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let old: PortBinding = from_py(old)?;
        let new: PortBinding = from_py(new)?;
        let inner = self.inner.clone();
        unit_future(
            py,
            async move { inner.replace_desired_port(&old, &new).await },
        )
    }

    // Network.

    /// The network rules that apply to this sandbox.
    fn network_rules<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.network_rules().await })
    }

    /// Allows hosts for this sandbox only.
    fn allow_hosts<'py>(&self, py: Python<'py>, hosts: Vec<String>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.allow_hosts(hosts).await })
    }

    /// Denies hosts for this sandbox only.
    fn deny_hosts<'py>(&self, py: Python<'py>, hosts: Vec<String>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.deny_hosts(hosts).await })
    }

    /// Removes the rules of this sandbox on hosts.
    fn remove_hosts<'py>(
        &self,
        py: Python<'py>,
        hosts: Vec<String>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.remove_hosts(hosts).await })
    }

    /// Removes the rule `id` of this sandbox.
    fn remove_network_rule<'py>(&self, py: Python<'py>, id: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.remove_network_rule(&id).await })
    }

    // Credentials.

    /// Pushes a credentials update: custom secrets, service credentials and
    /// their sources. Resolves to the outcome, with the services the daemon
    /// withholds.
    fn push_credentials<'py>(
        &self,
        py: Python<'py>,
        update: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let update: CredentialsUpdate = from_py(update)?;
        let inner = self.inner.clone();
        serde_future(py, async move { inner.push_credentials(&update).await })
    }

    /// Sets the secret of `service` for this sandbox; the proxy adds it to
    /// requests, the sandbox never sees it. Resolves to the outcome, with the
    /// services the daemon withholds.
    fn push_service_secret<'py>(
        &self,
        py: Python<'py>,
        service: String,
        value: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move {
            inner.push_service_secret(&service, value).await
        })
    }

    /// Removes the secret of `service` for this sandbox. Resolves to the
    /// outcome.
    fn remove_service_secret<'py>(
        &self,
        py: Python<'py>,
        service: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(
            py,
            async move { inner.remove_service_secret(&service).await },
        )
    }

    // Kits.

    /// Installs a kit artifact in place, in the running container.
    fn add_kit_artifact<'py>(
        &self,
        py: Python<'py>,
        artifact: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let artifact: Value = from_py(artifact)?;
        let inner = self.inner.clone();
        unit_future(py, async move { inner.add_kit_artifact(&artifact).await })
    }

    /// Replaces the container with one built with more kits.
    fn swap_container<'py>(
        &self,
        py: Python<'py>,
        request: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let request: SwapRequest = from_py(request)?;
        let inner = self.inner.clone();
        serde_future(py, async move { inner.swap_container(&request).await })
    }

    // MCP.

    /// The MCP gateway of the sandbox.
    fn mcp_gateway<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.mcp_gateway().await })
    }

    /// Loads the registered MCP server `server` into the gateway.
    fn load_mcp_server<'py>(&self, py: Python<'py>, server: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        serde_future(py, async move { inner.load_mcp_server(&server).await })
    }

    /// Unloads the MCP server `server` from the gateway.
    fn unload_mcp_server<'py>(
        &self,
        py: Python<'py>,
        server: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        unit_future(py, async move { inner.unload_mcp_server(&server).await })
    }

    // SSH.

    /// An SSH connection to the sandbox, as a byte tunnel.
    fn ssh_tunnel<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        class_future(
            py,
            async move { inner.ssh_tunnel().await.map(SshTunnel::new) },
        )
    }
}
