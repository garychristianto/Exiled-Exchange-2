# How this works

There are 2 main parts of the app:

1. renderer: this is the HTML/Javascript-based UI rendered within the Electron container. This runs Vue.js, a React-like Javascript framework for rendering front-end.
2. main: includes the main app (written in Electron). Handles keyboard shortcuts, brings up the UI and overlays.

Note that these 2 both depend on each other, and one cannot run without the other.

# How to develop

The most up-to-date instructions can always be derived from CI:

[.github/workflows/main.yml](https://github.com/Kvan7/exiled-exchange-2/blob/master/.github/workflows/main.yml)

Here's what that looks like as of 2023-12-03.

```shell
cd renderer
npm install
npm run make-index-files
npm run dev

# In a second shell
cd main
npm install
npm run dev
```

## Formatting

```shell
cd renderer
npm run format
```

# How to build

```shell
cd renderer
npm install
npm run make-index-files
npm run build

cd ../main
npm install
npm run build
# We want to sign with a distribution certificate to ensure other users can
# install without errors
CSC_NAME="Certificate name in Keychain" npm run package
```

# How to release a build

Releases on this fork are fully automated by `.github/workflows/release.yml`:
pushing a `vX.Y.Z` tag builds Windows/Linux/macOS and publishes a GitHub
Release on this fork, which the app's auto-updater then picks up.

1. Bump the version in `main/package.json` (keep it consistent across the repo —
   `versionCheck.py` runs in pre-commit and CI).
2. `npm i` in renderer & main (updates `package-lock.json` with the new version).
3. Commit the bumped version and `git push`.
4. Tag it **to match the version** and push the tag:
   ```shell
   git tag v0.16.0   # must equal main/package.json version
   git push origin v0.16.0
   ```
5. The Release workflow builds all platforms, uploads the installers +
   `latest*.yml` to a draft release, then publishes it as "latest". No manual
   draft/publish step needed.

Requirements (one-time, on the fork):
- Settings → Actions → General → Workflow permissions → **Read and write**, so CI
  can create the release.

> The local `# How to build` steps above are only needed for testing a build on
> your own machine; the Release workflow does the packaging for distribution.

# How to build yourself

```shell
sh testUpdate.sh
```

Read the contents of `testUpdate.sh` to understand what it does. Running random scripts from the internet is not recommended so you really should read the code before running it.
