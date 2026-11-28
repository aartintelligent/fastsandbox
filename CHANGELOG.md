# Changelog

## [0.2.0](https://github.com/aartintelligent/fastsandbox/compare/v0.1.3...v0.2.0) (2026-11-28)


### ⚠ BREAKING CHANGES

* KitCache no longer compiles with the sbx CLI unless given it, and keeps its packages in memory unless given a directory; KitPackage.dir and PackageImage.path are None for a package held in memory.

### Added

* forge kits without the sbx CLI by default ([#11](https://github.com/aartintelligent/fastsandbox/issues/11)) ([5355a4f](https://github.com/aartintelligent/fastsandbox/commit/5355a4f6645b546602ed28486d1b9ecee850d232))
* give the agent MCP servers through a mixin ([#13](https://github.com/aartintelligent/fastsandbox/issues/13)) ([0b0df2e](https://github.com/aartintelligent/fastsandbox/commit/0b0df2ee68cce1585d82d4a46d2834f47b0a0d04))
* move to docker-sandbox 0.3.0 and report withheld credentials ([#9](https://github.com/aartintelligent/fastsandbox/issues/9)) ([388b0cc](https://github.com/aartintelligent/fastsandbox/commit/388b0cc099ccf3c5c3f286bb8693234cebcf481c))
* write kit mixins in Python ([#12](https://github.com/aartintelligent/fastsandbox/issues/12)) ([18df267](https://github.com/aartintelligent/fastsandbox/commit/18df26792d8777501aea1e6b1b165a5e77b45b6d))


### Fixed

* give the path of an error as a string, as documented ([#20](https://github.com/aartintelligent/fastsandbox/issues/20)) ([58657ef](https://github.com/aartintelligent/fastsandbox/commit/58657ef886b0d7948c310b405b32d460953741b7))
* **kits:** keep the packages of a kit cache apart and compiled when asked ([#19](https://github.com/aartintelligent/fastsandbox/issues/19)) ([64e8408](https://github.com/aartintelligent/fastsandbox/commit/64e8408bd77b8c165b1c4f4a9d168ffcb848c162))
* **kits:** read the images of a package kept in a directory ([#14](https://github.com/aartintelligent/fastsandbox/issues/14)) ([9d06fee](https://github.com/aartintelligent/fastsandbox/commit/9d06fee08d30c61023f9f82ef65ef58ae9fbe990))
* **tasks:** report the credentials the daemon withholds from the sandbox of a run ([#18](https://github.com/aartintelligent/fastsandbox/issues/18)) ([d6574c0](https://github.com/aartintelligent/fastsandbox/commit/d6574c0734d0bc34ce0c45cde5db5f4821544e0b))


### Documentation

* align the pages with the host checks and withheld credentials of 0.2.0 ([#16](https://github.com/aartintelligent/fastsandbox/issues/16)) ([0c1b084](https://github.com/aartintelligent/fastsandbox/commit/0c1b084e462e1a3c2672f5d57b448bbc3aa69e2e))
* **examples:** check the MCP server of agent-kit-forge with the client of the examples ([#17](https://github.com/aartintelligent/fastsandbox/issues/17)) ([3d37679](https://github.com/aartintelligent/fastsandbox/commit/3d3767903b86f6c2b0570a283d3d2dd977a15543))
* **examples:** show the forge, kit mixins in Python and withheld credentials ([#15](https://github.com/aartintelligent/fastsandbox/issues/15)) ([4c36913](https://github.com/aartintelligent/fastsandbox/commit/4c3691302a886fd810d77a4000ac8219c06d93c5))

## [0.1.3](https://github.com/aartintelligent/fastsandbox/compare/v0.1.2...v0.1.3) (2026-11-26)


### Added

* support Python 3.12 and 3.13 ([#7](https://github.com/aartintelligent/fastsandbox/issues/7)) ([863b047](https://github.com/aartintelligent/fastsandbox/commit/863b04744de70978cc147ffc4f4e24dcfaa41db4))

## [0.1.2](https://github.com/aartintelligent/fastsandbox/compare/v0.1.1...v0.1.2) (2026-11-26)


### Documentation

* rewrite the README for users, with badges ([#5](https://github.com/aartintelligent/fastsandbox/issues/5)) ([cfcc4da](https://github.com/aartintelligent/fastsandbox/commit/cfcc4dafc82acdb38329d090f7cbeea8aa119121))

## [0.1.1](https://github.com/aartintelligent/fastsandbox/compare/v0.1.0...v0.1.1) (2026-11-25)


### Documentation

* align the pages and docstrings with the code ([#2](https://github.com/aartintelligent/fastsandbox/issues/2)) ([f672a94](https://github.com/aartintelligent/fastsandbox/commit/f672a9478bb3d9fc6a50ba2afdd1dd433b730301))

## 0.1.0 (2026-11-25)


### Added

* first release of fastsandbox ([3af1f89](https://github.com/aartintelligent/fastsandbox/commit/3af1f89ae997eefc4b4e6c7b6a8d314a705d42ad))
