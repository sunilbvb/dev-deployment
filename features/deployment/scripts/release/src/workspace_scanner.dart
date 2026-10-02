import 'dart:io';
import 'git_ops.dart';
import 'models.dart';

const _maxScanDepth = 5;
const _skipDirs = {
  'build', 'node_modules', 'Pods', 'example', 'examples', 'ephemeral', 'DerivedData',
};
const _projectInternalDirs = {
  'android', 'ios', 'macos', 'linux', 'windows', 'web', 'lib', 'test',
  'integration_test', 'test_driver', 'assets', 'fonts', 'bin',
};

Set<String> extractDependencyNames(String pubspecContent) {
  final deps = <String>{};
  final lines = pubspecContent.split('\n');
  bool inDeps = false;

  for (final line in lines) {
    if (RegExp(r'^(dependencies|dev_dependencies):').hasMatch(line)) {
      inDeps = true;
      continue;
    }
    if (inDeps) {
      if (RegExp(r'^[a-zA-Z0-9_-]+:').hasMatch(line)) {
        inDeps = false;
        continue;
      }
      final depMatch = RegExp(r'^\s{2}([a-zA-Z0-9_-]+):').firstMatch(line);
      if (depMatch != null) {
        deps.add(depMatch.group(1)!);
      }
    }
  }
  return deps;
}

/// Scan all apps and packages in workspace
Future<Map<String, PackageInfo>> scanWorkspacePackages(
  String workspaceRoot,
) async {
  final packages = <String, PackageInfo>{};

  void addPackage(File pubspec, String relPath) {
    final content = pubspec.readAsStringSync();
    final nameMatch = RegExp(
      r'^name:\s*([a-zA-Z0-9_-]+)',
      multiLine: true,
    ).firstMatch(content);
    if (nameMatch == null) return;
    final versionMatch = RegExp(
      r'^version:\s*([0-9a-zA-Z\.\+\-]+)',
      multiLine: true,
    ).firstMatch(content);
    final name = nameMatch.group(1)!;
    packages.putIfAbsent(
      name,
      () => PackageInfo(
        name: name,
        relativePath: relPath,
        absolutePath: pubspec.parent.path,
        version: versionMatch?.group(1),
        directDependencies: extractDependencyNames(content),
      ),
    );
  }

  // The root is a project of its own unless it only aggregates workspace members.
  final rootPubspec = File('$workspaceRoot/pubspec.yaml');
  if (rootPubspec.existsSync() &&
      !RegExp(r'^workspace:', multiLine: true).hasMatch(rootPubspec.readAsStringSync())) {
    addPackage(rootPubspec, '.');
  }

  void walk(Directory dir, int depth) {
    if (depth > _maxScanDepth) return;
    List<FileSystemEntity> children;
    try {
      children = dir.listSync(followLinks: false)
        ..sort((a, b) => a.path.compareTo(b.path));
    } on FileSystemException {
      return;
    }
    final isProject = depth > 0 && File('${dir.path}/pubspec.yaml').existsSync();
    if (isProject) {
      addPackage(File('${dir.path}/pubspec.yaml'), dir.path.substring(workspaceRoot.length + 1));
    }
    for (final child in children) {
      if (child is! Directory) continue;
      final name = child.uri.pathSegments.where((s) => s.isNotEmpty).last;
      if (name.startsWith('.') || _skipDirs.contains(name)) continue;
      // Inside a project, platform/source folders never hold sibling projects.
      if ((isProject || depth == 0 && rootPubspec.existsSync()) && _projectInternalDirs.contains(name)) {
        continue;
      }
      walk(child, depth + 1);
    }
  }

  walk(Directory(workspaceRoot), 0);
  return packages;
}

/// Whether [file] (relative to the workspace root) belongs to [pkg]. A package
/// at "." (the workspace root) owns everything not owned by a nested package.
bool isInPackage(String file, PackageInfo pkg, Iterable<PackageInfo> all) {
  bool under(String path) => file == path || file.startsWith('$path/');
  if (pkg.relativePath == '.') {
    return !all.any((p) => p.relativePath != '.' && under(p.relativePath));
  }
  if (!under(pkg.relativePath)) return false;
  // A nested package (e.g. profile/profile_logic) owns its files, not the parent.
  return !all.any((p) =>
      p.relativePath != pkg.relativePath &&
      p.relativePath.startsWith('${pkg.relativePath}/') &&
      under(p.relativePath));
}

/// Recursively resolve internal workspace dependencies for an app/package
List<PackageInfo> resolveInternalDependencies(
  PackageInfo rootPackage,
  Map<String, PackageInfo> allPackages,
) {
  final resolved = <String, PackageInfo>{};

  void resolve(PackageInfo current) {
    for (final depName in current.directDependencies) {
      if (depName != rootPackage.name &&
          allPackages.containsKey(depName) &&
          !resolved.containsKey(depName)) {
        final depPkg = allPackages[depName]!;
        if (depPkg.relativePath.startsWith('packages/')) {
          resolved[depName] = depPkg;
          resolve(depPkg);
        }
      }
    }
  }

  resolve(rootPackage);
  return resolved.values.toList();
}

/// Scan and print unreleased status for all workspace packages
Future<void> runWorkspaceStatusReport(
  String workspaceRoot,
  Map<String, PackageInfo> packages,
) async {
  print('📊 ──────────────── WORKSPACE UNRELEASED REPORT ────────────────');
  var foundAny = false;

  final workspaceGitRootRes = await runGit([
    'rev-parse',
    '--show-toplevel',
  ], workspaceRoot);
  final workspaceGitRoot = workspaceGitRootRes.exitCode == 0
      ? workspaceGitRootRes.stdout.toString().trim()
      : workspaceRoot;

  for (final pkg in packages.values) {
    // Apps that are their own separate Git repository (see resolveGitRoot doc comment)
    // must be scanned in THAT repo, not the outer workspace repo.
    final pkgGitRoot = await resolveGitRoot(
      '$workspaceRoot/${pkg.relativePath}',
    );
    final pkgHasOwnRepo = pkgGitRoot != null && pkgGitRoot != workspaceGitRoot;
    final pkgRepoRoot = pkgHasOwnRepo ? pkgGitRoot : workspaceRoot;

    final latestTag = await findLatestTagForTarget(pkg.name, pkgRepoRoot);
    final commits = await getAllCommitsInRange(
      workspaceRoot: pkgRepoRoot,
      fromTag: latestTag,
    );
    final pkgCommits = pkgHasOwnRepo
        ? commits
        : commits
              .where(
                (c) =>
                    c.changedFiles.any((f) => isInPackage(f, pkg, packages.values)),
              )
              .toList();

    if (pkgCommits.isNotEmpty) {
      foundAny = true;
      print('📦 \x1B[1m${pkg.name}\x1B[0m (${pkg.relativePath})');
      print(
        '   Last Tag: ${latestTag ?? 'None'} | Unreleased Commits: \x1B[33m${pkgCommits.length}\x1B[0m',
      );
      for (final c in pkgCommits.take(3)) {
        print('   - ${c.subject} (\x1B[36m${c.shortHash}\x1B[0m)');
      }
      if (pkgCommits.length > 3)
        print('   ... and ${pkgCommits.length - 3} more commits.');
      print('');
    }
  }

  if (!foundAny) {
    print(
      '✨ All apps and packages are up to date with their latest release tags.',
    );
  }
  print('─────────────────────────────────────────────────────────────────');
}
