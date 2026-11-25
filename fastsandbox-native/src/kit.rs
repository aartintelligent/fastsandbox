//! Compiled kit packages, the agent they describe, and the kit compiler.
//!
//! A kit package is what `sbx create` would send for a kit, captured once by
//! the compiler (which runs the `sbx` CLI behind a capturing proxy) and
//! replayed through the socket alone afterwards.

use std::collections::BTreeMap;
use std::path::PathBuf;

use docker_sandbox::kit::{CompileJob, KitAgent as LibAgent, KitPackage as LibPackage};
use docker_sandbox::sandbox::CreateRequest;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde_json::Value;

use crate::client::Client;
use crate::convert::{class_future, from_py, optional_duration, serde_future, to_py};
use crate::sandbox::Sandbox;

/// A compiled kit package, opened from its directory.
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

    /// The directory of the package.
    #[getter]
    fn dir(&self) -> PathBuf {
        self.inner.dir().to_path_buf()
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
                item.set_item("path", &image.path)?;
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
        format!(
            "KitPackage(dir={:?})",
            self.inner.dir().display().to_string()
        )
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
    inner: docker_sandbox::kit::KitCompiler,
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
        let mut inner = docker_sandbox::kit::KitCompiler::new(sbx, client.inner.clone(), work_dir);
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
        class_future(py, async move {
            inner.compile(&job).await.map(|inner| KitPackage { inner })
        })
    }
}
