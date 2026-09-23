# Generic Git bootstrap boundary

`tool.scad-project` owns SCAD-specific project, build, design, verification and reusable-workflow behaviour.

Generic repository bootstrap and dependency/submodule management is owned by [`tool.git-project`](https://github.com/brainboxemb/tool.git-project).

The target current-generation consumer structure is:

```text
tools/tool.git-project       pinned bootstrap gitlink
project.yml                  generic project/profile/dependency declaration
project.scad.yml             SCAD-specific configuration
tools/tool.scad-project      managed SCAD tooling dependency

bootstrap.ps1 / bootstrap.sh generic managed bootstrap launchers
update.ps1 / update.sh       generic managed update/status launchers
```

Root bootstrap/update launchers come from `tool.git-project`; this repository does not maintain a second updater implementation.

After a generic dependency update, `consumer/post-update.ps1` or
`consumer/post-update.sh` performs the SCAD-specific follow-up: align
brainboxemb `tool.scad-project` reusable-workflow refs with the semantic
release configured in `project.yml`.

Current consumer operating guidance belongs in the shared SCAD repository-development guide in `brainboxemb.meta` plus the consumer's local `doc/01-development.md`.
