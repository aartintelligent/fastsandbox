//! Kit packages, the agent they describe, the kit forge and the kit compiler.
//!
//! A kit package is what `sbx create` would send for a kit, replayed through
//! the socket alone. The forge writes it without the `sbx` CLI, the base kit
//! rebuilt from its published image, in memory or into a directory; the
//! compiler captures it once from the CLI, run behind a capturing proxy.
//!
//! Mixins written in Python cross the boundary as their reference and their
//! descriptor in JSON: the crate checks them, as it checks those it reads
//! from a directory, so that its rules are written once. So do the mixins it
//! builds for MCP servers, which cross it as their name, URL and token
//! variable.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use docker_sandbox::kit::{ImageArchive, KitAgent as LibAgent, KitPackage as LibPackage};
use docker_sandbox::sandbox::CreateRequest;
use docker_sandbox_kit::{Agent, CompileJob, KitDescriptor, McpServer, Mixin};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde_json::Value;

use crate::client::Client;
use crate::convert::{from_py, optional_duration, serde_future, to_py};
use crate::sandbox::Sandbox;

/// A kit package: opened from its directory, compiled, or forged in memory.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct KitPackage {
    /// The package of the library.
    inner: LibPackage,
}

#[pymethods]
impl KitPackage {
    /// Opens the package compiled into `dir`.
    #[staticmethod]
    fn open(dir: PathBuf) -> PyResult<Self> {
        LibPackage::open(dir)
            .map(|inner| Self { inner })
            .map_err(crate::error::to_py)
    }

    /// The directory of the package, `None` for a package held in memory.
    #[getter]
    fn dir(&self) -> Option<PathBuf> {
        self.inner.dir().map(Path::to_path_buf)
    }

    /// The daemon API version the package was written for.
    #[getter]
    fn compiled_api(&self) -> Option<String> {
        self.inner.compiled_api().map(str::to_owned)
    }

    /// The `sbx` version the package was compiled with.
    #[getter]
    fn compiled_with(&self) -> Option<String> {
        self.inner.compiled_with().map(str::to_owned)
    }

    /// The kit references of the package.
    #[getter]
    fn kit_refs(&self) -> Vec<String> {
        self.inner.kit_refs()
    }

    /// The agent the base kit describes, if any.
    #[getter]
    fn agent(&self) -> Option<KitAgent> {
        self.inner.agent().map(|inner| KitAgent { inner })
    }

    /// The kit artifacts, as the daemon receives them.
    #[getter]
    fn kit_artifacts(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        to_py(py, &self.inner.kit_artifacts())
    }

    /// The image archives of the package: `{"path", "reference"}`.
    #[getter]
    fn images(&self, py: Python<'_>) -> PyResult<Vec<Py<PyAny>>> {
        self.inner
            .images()
            .iter()
            .map(|image| {
                let item = PyDict::new(py);
                // A package held in memory holds its images in memory: they
                // have no path.
                let path = match &image.archive {
                    ImageArchive::File(path) => Some(path),
                    _ => None,
                };
                item.set_item("path", path)?;
                item.set_item("reference", image.reference.as_deref())?;
                Ok(item.into_any().unbind())
            })
            .collect()
    }

    /// The creation request of a sandbox named `name` from this package.
    fn request(&self, py: Python<'_>, name: String) -> PyResult<Py<PyAny>> {
        let request = self.inner.request(name).map_err(crate::error::to_py)?;
        to_py(py, &request)
    }

    /// Loads the images of the package into the daemon; returns how many.
    fn load_images<'py>(&self, py: Python<'py>, client: &Client) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        let client = client.inner.clone();
        serde_future(py, async move { inner.load_images(&client).await })
    }

    /// Loads the images and creates the sandbox `name` from the package.
    fn create<'py>(
        &self,
        py: Python<'py>,
        client: &Client,
        name: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        let client = client.inner.clone();
        serde_future(py, async move { inner.create(&client, name).await })
    }

    /// Loads the images and creates a sandbox from a request of the package,
    /// adjusted by the caller.
    fn create_with<'py>(
        &self,
        py: Python<'py>,
        client: &Client,
        request: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let request: CreateRequest = from_py(request)?;
        let inner = self.inner.clone();
        let client = client.inner.clone();
        serde_future(
            py,
            async move { inner.create_with(&client, &request).await },
        )
    }

    /// Installs the kits of the package in place in a running sandbox;
    /// returns how many artifacts were installed.
    fn install_into<'py>(&self, py: Python<'py>, sandbox: &Sandbox) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        let sandbox = sandbox.inner.clone();
        serde_future(py, async move { inner.install_into(&sandbox).await })
    }

    /// Adds the kits of the package to a sandbox by swapping its container.
    fn add_to<'py>(&self, py: Python<'py>, sandbox: &Sandbox) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        let sandbox = sandbox.inner.clone();
        serde_future(py, async move { inner.add_to(&sandbox).await })
    }

    fn __repr__(&self) -> String {
        let dir = self
            .inner
            .dir()
            .map_or_else(|| "memory".to_owned(), |dir| dir.display().to_string());
        format!("KitPackage(dir={dir:?})")
    }
}

/// The agent a kit describes: its program, run options and network needs.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct KitAgent {
    /// The agent of the library.
    inner: LibAgent,
}

#[pymethods]
impl KitAgent {
    /// The agent described by a kit artifact, if it describes one.
    #[staticmethod]
    fn from_artifact(artifact: &Bound<'_, PyAny>) -> PyResult<Option<Self>> {
        let artifact: Value = from_py(artifact)?;
        Ok(LibAgent::from_artifact(&artifact).map(|inner| Self { inner }))
    }

    /// The name of the agent.
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    /// The display name of the agent.
    #[getter]
    fn display_name(&self) -> Option<&str> {
        self.inner.display_name.as_deref()
    }

    /// The program of the agent.
    #[getter]
    fn binary(&self) -> Option<&str> {
        self.inner.binary.as_deref()
    }

    /// The options the kit runs the agent with.
    #[getter]
    fn run_options(&self) -> Vec<String> {
        self.inner.run_options.clone()
    }

    /// The network entries the kit declares.
    #[getter]
    fn network(&self) -> Vec<String> {
        self.inner.network.clone()
    }

    /// The command line that runs the agent with `args`.
    fn command(&self, args: Vec<String>) -> Vec<String> {
        self.inner.command(args)
    }

    /// The hosts the agent needs to reach.
    fn hosts(&self) -> Vec<String> {
        self.inner.hosts()
    }

    fn __repr__(&self) -> String {
        format!("KitAgent(name={:?})", self.inner.name)
    }
}

/// Compiles kits into packages by running the `sbx` CLI once behind a
/// capturing proxy.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct KitCompiler {
    /// The compiler of the library.
    inner: docker_sandbox_kit::KitCompiler,
}

#[pymethods]
impl KitCompiler {
    /// A compiler that runs the `sbx` program `sbx`, for the daemon of
    /// `client`, with its scratch files in `work_dir`; `timeout` (seconds)
    /// bounds a compilation.
    #[new]
    #[pyo3(signature = (sbx, client, work_dir, timeout=None))]
    fn new(
        sbx: PathBuf,
        client: &Client,
        work_dir: PathBuf,
        timeout: Option<f64>,
    ) -> PyResult<Self> {
        let mut inner = docker_sandbox_kit::KitCompiler::new(sbx, client.inner.clone(), work_dir);
        if let Some(timeout) = optional_duration(timeout)? {
            inner = inner.with_timeout(timeout);
        }
        Ok(Self { inner })
    }

    /// Compiles the kit `base`, with `mixins` and kit `args`, into the
    /// package directory `output`.
    #[pyo3(signature = (base, output, mixins=Vec::new(), args=BTreeMap::new()))]
    fn compile<'py>(
        &self,
        py: Python<'py>,
        base: String,
        output: PathBuf,
        mixins: Vec<String>,
        args: BTreeMap<String, String>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let mut job = CompileJob::new(base, output);
        for mixin in mixins {
            job = job.with_mixin(mixin);
        }
        for (name, value) in args {
            job = job.with_arg(name, value);
        }
        let inner = self.inner.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            inner
                .compile(&job)
                .await
                .map(|inner| KitPackage { inner })
                .map_err(crate::error::kit_to_py)
        })
    }
}

/// A mixin given to the forge: one written in Python, or the directory of one.
#[derive(Debug, FromPyObject)]
pub(crate) enum MixinArg {
    /// The reference and the descriptor, in JSON, of a mixin written in
    /// Python.
    Written(String, String),
    /// The directory of a mixin, described by its `spec.yaml`.
    Dir(PathBuf),
}

impl MixinArg {
    /// The mixin of the crate, checked as the forge checks it.
    fn into_mixin(self) -> PyResult<Mixin> {
        match self {
            Self::Written(reference, descriptor) => written(reference, &descriptor),
            Self::Dir(dir) => Mixin::read(dir).map_err(crate::error::kit_to_py),
        }
    }
}

/// The mixin of the JSON `descriptor`, listed under `reference`, checked as
/// the forge checks it.
fn written(reference: String, descriptor: &str) -> PyResult<Mixin> {
    let value = serde_json::from_str(descriptor)
        .map_err(|error| PyValueError::new_err(format!("descriptor is not JSON: {error}")))?;
    let descriptor = KitDescriptor::from_json(value).map_err(crate::error::kit_to_py)?;
    Mixin::new(reference, descriptor).map_err(crate::error::kit_to_py)
}

/// Checks the mixin of the JSON `descriptor`, listed under `reference`, as
/// the forge checks it.
///
/// # Errors
///
/// Raises `InvalidKitError` when the forge would refuse the mixin.
#[pyfunction]
pub(crate) fn check_mixin(reference: String, descriptor: &str) -> PyResult<()> {
    written(reference, descriptor).map(drop)
}

/// The mixin of the directory `dir`: its reference, the canonical path of the
/// directory, and its descriptor in JSON.
///
/// # Errors
///
/// Raises when the directory or its `spec.yaml` cannot be read, and
/// `InvalidKitError` when the forge would refuse the descriptor.
#[pyfunction]
pub(crate) fn read_mixin(dir: PathBuf) -> PyResult<(String, String)> {
    Mixin::read(dir)
        .map(|mixin| parts(&mixin))
        .map_err(crate::error::kit_to_py)
}

/// The reference of `mixin` and its descriptor in JSON, as Python receives
/// them.
fn parts(mixin: &Mixin) -> (String, String) {
    (
        mixin.reference().to_owned(),
        mixin.descriptor().to_json().to_string(),
    )
}

/// The descriptor of the text of a `spec.yaml` written in JSON, in JSON.
///
/// # Errors
///
/// Raises `InvalidKitError` when the text is not JSON, or not a v3 mixin the
/// forge takes.
#[pyfunction]
pub(crate) fn parse_descriptor(text: &str) -> PyResult<String> {
    KitDescriptor::parse(text)
        .map(|descriptor| descriptor.to_json().to_string())
        .map_err(crate::error::kit_to_py)
}

/// An MCP server as it crosses the boundary: its name, the URL of its
/// endpoint, and the variable of its bearer token, if it takes one.
type ServerParts = (String, String, Option<String>);

/// The MCP server named `name` that a process of the host serves on `port` of
/// its loopback: its name, its URL as the sandbox reaches it, and the
/// variable of its bearer token.
#[pyfunction]
pub(crate) fn mcp_host_server(name: String, port: u16) -> ServerParts {
    let server = McpServer::host(name, port);
    (
        server.name().to_owned(),
        server.url().to_owned(),
        server.token_env().map(str::to_owned),
    )
}

/// The mixin that registers `servers` in the configuration of the agent
/// named `agent`, built by the crate: its reference and its descriptor in
/// JSON.
///
/// # Errors
///
/// Raises `InvalidKitError` for an agent `sbx` does not know or one without an
/// MCP adapter, no server, two servers of the same name, or a name, a URL or
/// a variable the crate refuses.
#[pyfunction]
pub(crate) fn mcp_mixin(agent: &str, servers: Vec<ServerParts>) -> PyResult<(String, String)> {
    let agent: Agent = agent.parse().map_err(crate::error::kit_to_py)?;
    let servers = servers.into_iter().map(|(name, url, token_env)| {
        let server = McpServer::remote(name, url);
        match token_env {
            Some(env) => server.with_bearer_env(env),
            None => server,
        }
    });
    Mixin::mcp(agent, servers)
        .map(|mixin| parts(&mixin))
        .map_err(crate::error::kit_to_py)
}

/// Forges kit packages without the `sbx` CLI, through the socket alone: the
/// base kit rebuilt from its published image, the mixins written in Python or
/// read from their directories.
#[pyclass(frozen, module = "fastsandbox._native")]
#[derive(Debug, Clone)]
pub(crate) struct KitForge {
    /// The client of the daemon the packages are forged for.
    client: docker_sandbox::Client,
}

#[pymethods]
impl KitForge {
    /// A forge for the daemon of `client`.
    #[new]
    fn new(client: &Client) -> Self {
        Self {
            client: client.inner.clone(),
        }
    }

    /// Forges the published kit `base`, e.g. `docker.io/sbx/shell:latest`,
    /// with `mixins`, written in Python or directories, and kit `args`: in
    /// memory, or into the package directory `output` when given.
    ///
    /// # Errors
    ///
    /// Fails, before anything is sent, when a mixin directory cannot be read
    /// or a mixin holds a descriptor the forge refuses.
    #[pyo3(signature = (base, mixins=Vec::new(), args=BTreeMap::new(), output=None))]
    fn forge<'py>(
        &self,
        py: Python<'py>,
        base: String,
        mixins: Vec<MixinArg>,
        args: BTreeMap<String, String>,
        output: Option<PathBuf>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let mut forge = docker_sandbox_kit::KitForge::new(self.client.clone()).with_base(base);
        for mixin in mixins {
            forge = forge.with_mixin(mixin.into_mixin()?);
        }
        for (name, value) in args {
            forge = forge.with_arg(name, value);
        }
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let package = match output {
                Some(dir) => forge.forge(dir).await,
                None => forge.build().await,
            };
            package
                .map(|inner| KitPackage { inner })
                .map_err(crate::error::kit_to_py)
        })
    }
}
