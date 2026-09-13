# Generic Git bootstrap boundary

`tool.scad-project` owns SCAD-specific project, build, design, verification and reusable-workflow behaviour.

Generic repository bootstrap and dependency/submodule management is owned by [`tool.git-project`](https://github.com/brainboxemb/tool.git-project).

The target current-generation consumer structure is:

```text
tools/tool.git-project       pinned bootstrap gitlink
project.yml                  generic project/profile/dependency declaration
project.scad.yml             SCAD-specific configuration
tools/tool.scad-project      managed SCAD tooling dependency
```

Root bootstrap/update launchers delegate generic Git work to `tool.git-project`. SCAD-specific tasks such as keeping reusable `tool.scad-project` workflow callers aligned to the checked-out tool commit remain in this repository.

This boundary is the prerequisite described as Step 0.5 in `meta.scad-projects/docs/tooling-test-plan.md`.
