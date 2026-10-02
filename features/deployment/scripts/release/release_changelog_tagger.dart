#!/usr/bin/env dart

import 'dart:io';

import 'src/models.dart';
import 'src/semver_ops.dart';
import 'src/store_notes.dart';
import 'src/git_ops.dart';
import 'src/branch_governance.dart';
import 'src/workspace_scanner.dart';
import 'src/changelog_builder.dart';
import 'src/release_notifier.dart';

export 'src/models.dart';
export 'src/semver_ops.dart';
export 'src/store_notes.dart';
export 'src/git_ops.dart';
export 'src/branch_governance.dart';
export 'src/workspace_scanner.dart';
export 'src/changelog_builder.dart';
export 'src/release_notifier.dart';

/// Release Changelog & Git Tag Automation Tool for Melos Monorepos
///
/// Complete Operational Suite:
/// ── Core Lifecycle Modes ──
/// 1. preview   : Analyze app & packages + print terminal preview (Dry-run, zero changes).
/// 2. changelog : Analyze + print preview + update CHANGELOG.md files (No git commit/tag).
/// 3. commit    : Analyze + print preview + update CHANGELOG.md + Git commit.
/// 4. tag       : Analyze + print preview + update CHANGELOG.md + Git commit + Local annotated Git tag (DEFAULT).
/// 5. push      : Analyze + print preview + update CHANGELOG.md + Git commit + Local Git tag + Remote push.
///
/// ── Advanced Operations ──
/// 6. status    : Scan workspace and report unreleased commits across ALL apps & packages.
/// 7. bump      : Auto-bump SemVer (patch/minor/major/build) in pubspec.yaml before release.
/// 8. store     : Generate consumer-friendly App Store / Play Store "What's New" release notes.
/// 9. notify    : Broadcast compiled release changelog to Google Chat / Slack webhook.
/// 10. verify   : Run static analysis & unit tests on target and modified dependencies before release.
/// 11. undo     : Cleanly delete accidental Git tag and revert changelog commit.
void main(List<String> rawArgs) async {
  final options = parseArgs(rawArgs);

  if (options.showHelp) {
    printHelp();
    exit(0);
  }

  final workspaceRoot = options.workspaceRoot ?? Directory.current.path;
  print('🔍 Monorepo Workspace: $workspaceRoot');

  // Verify git repository
  final isGit = await runGit([
    'rev-parse',
    '--is-inside-work-tree',
  ], workspaceRoot);
  if (isGit.exitCode != 0) {
    stderr.writeln(
      '❌ Error: Workspace is not a Git repository at $workspaceRoot',
    );
    exit(1);
  }

  // Works for Melos/pub workspaces, a single project at the root, and plain
  // folders of apps/packages — a root pubspec.yaml is not required.
  final workspacePackages = await scanWorkspacePackages(workspaceRoot);
  if (workspacePackages.isEmpty) {
    stderr.writeln('❌ Error: No Dart/Flutter projects (pubspec.yaml) found under $workspaceRoot');
    exit(1);
  }

  // -------------------------------------------------------------
  // OPERATION: Workspace Status / Unreleased Scan
  // -------------------------------------------------------------
  if (options.showStatus) {
    await runWorkspaceStatusReport(workspaceRoot, workspacePackages);
    return;
  }

  if (options.appName == null && options.packageName == null && !options.all) {
    printHelp();
    exit(1);
  }

  final targetName = options.appName ?? options.packageName!;
  PackageInfo? targetInfo = workspacePackages[targetName];

  if (targetInfo == null) {
    for (final pkg in workspacePackages.values) {
      final dirName = pkg.relativePath.split('/').last;
      if (pkg.relativePath == targetName ||
          pkg.relativePath == 'apps/$targetName' ||
          pkg.relativePath == 'packages/$targetName' ||
          dirName.toLowerCase() == targetName.toLowerCase() ||
          pkg.name.toLowerCase() == targetName.toLowerCase()) {
        targetInfo = pkg;
        break;
      }
    }
  }

  if (targetInfo == null) {
    stderr.writeln(
      '❌ Error: Target "$targetName" not found in workspace packages.',
    );
    stderr.writeln('Available packages / apps:');
    for (final p in workspacePackages.values) {
      stderr.writeln('  - ${p.relativePath} (name: ${p.name})');
    }
    exit(1);
  }

  final target = targetInfo;

  // Detect whether the target lives in its OWN Git repository (e.g. apps/* are
  // gitignored at the monorepo root and cloned separately) rather than being a
  // plain subdirectory of the outer workspace repo. When it is, every git-history
  // operation concerning the target must run inside ITS repo, not the workspace's.
  final workspaceGitRootRes = await runGit([
    'rev-parse',
    '--show-toplevel',
  ], workspaceRoot);
  final workspaceGitRoot = workspaceGitRootRes.exitCode == 0
      ? workspaceGitRootRes.stdout.toString().trim()
      : workspaceRoot;
  final targetGitRoot = await resolveGitRoot(
    '$workspaceRoot/${target.relativePath}',
  );
  final targetHasOwnRepo =
      targetGitRoot != null && targetGitRoot != workspaceGitRoot;
  final appRepoRoot = targetHasOwnRepo ? targetGitRoot : workspaceRoot;

  if (targetHasOwnRepo) {
    print(
      '📦 ${target.name} is a separate Git repository at $appRepoRoot — scoping Git operations to it.',
    );
  }

  // -------------------------------------------------------------
  // OPERATION: Undo / Rollback Release
  // -------------------------------------------------------------
  if (options.undo) {
    final version = options.version ?? target.version ?? '1.0.0';
    final tagName =
        '${target.name}-v$version${flavorTagSuffix(options.flavor) ?? ''}';
    await runReleaseUndo(appRepoRoot, target, tagName);
    return;
  }

  print('🎯 Target: ${target.name} (${target.relativePath})');
  print(
    '⚙️ Execution Mode: ${options.modeDescription} [${options.mode.name.toUpperCase()}]',
  );

  // Resolve dependent local packages if it is an app
  final internalDeps = resolveInternalDependencies(target, workspacePackages);
  if (internalDeps.isNotEmpty) {
    print('🔗 Dependent Workspace Packages (${internalDeps.length}):');
    for (final dep in internalDeps) {
      print('   - ${dep.name} (${dep.relativePath})');
    }
  } else {
    print('ℹ️ No internal workspace dependencies found.');
  }

  // -------------------------------------------------------------
  // OPERATION: Version Bumping (SemVer: patch, minor, major, build)
  // -------------------------------------------------------------
  String version = options.version ?? target.version ?? '1.0.0';
  if (options.bumpType != null) {
    final newVersion = bumpSemVer(version, options.bumpType!);
    print(
      '📈 Bumped Version [${options.bumpType!.toUpperCase()}]: $version ➔ $newVersion',
    );
    version = newVersion;
    if (options.mode != ReleaseMode.preview) {
      final pubspecFile = File(
        '$workspaceRoot/${target.relativePath}/pubspec.yaml',
      );
      updatePubspecVersion(pubspecFile, newVersion);
      print('✅ Updated version in ${target.relativePath}/pubspec.yaml');
    }
  }

  final flavorSuffix = flavorTagSuffix(options.flavor);
  final tagName = '${target.name}-v$version${flavorSuffix ?? ''}';
  if (flavorSuffix != null) {
    print('🏳️ Environment: ${options.flavor} (tag suffix: $flavorSuffix)');
  }
  print('🏷️ Target Release Tag: $tagName (Version: $version)');

  // Determine previous tag — looked up in the target's OWN repo when it has one,
  // since that's the repo the tag would actually have been created in. When an
  // environment/flavor is in play, only that flavor's own prior tag counts as
  // "previous release" — a QA release shouldn't compute its changelog against
  // the last PROD tag, or vice versa.
  String? fromTag = options.fromTag;
  if (fromTag == null) {
    fromTag = await findLatestTagForTarget(
      target.name,
      appRepoRoot,
      flavorSuffix: flavorSuffix,
    );
    if (fromTag != null) {
      print(
        '⏮️ Found Previous Tag: $fromTag (Scanning window: $fromTag ➔ ${options.toRef})',
      );
    } else {
      print(
        'ℹ️ No previous tag found for ${target.name}. Scanning entire commit timeline (Inception ➔ ${options.toRef}).',
      );
    }
  } else {
    print(
      '⏮️ User-specified From Tag: $fromTag (Scanning window: $fromTag ➔ ${options.toRef})',
    );
  }

  // A release made locally (e.g. "Bump Patch", "Local Git Tag") is pushed as-is by Full
  // Release, instead of being rejected as a duplicate tag.
  if (options.mode == ReleaseMode.push && !options.force &&
      await isUnpushedLocalReleaseAtHead(tagName, appRepoRoot)) {
    print('ℹ️ Tag $tagName already exists locally on the current commit and is not on the remote yet — pushing it.');
    await pushExistingRelease(tagName: tagName, repoRoot: appRepoRoot);
    return;
  }

  // -------------------------------------------------------------
  // BRANCH GOVERNANCE & INTEGRITY GUARDS
  // -------------------------------------------------------------
  await validateBranchGovernance(
    workspaceRoot: appRepoRoot,
    target: target,
    tagName: tagName,
    options: options,
    fromTag: fromTag,
  );

  // -------------------------------------------------------------
  // COMPREHENSIVE TIMELINE SCAN: Capture ALL commits in release window
  // -------------------------------------------------------------
  // When the target has its own repo, ITS commits come exclusively from that repo —
  // every commit found there already belongs to the target, no path/mention matching
  // needed.
  final targetCommits = await getAllCommitsInRange(
    workspaceRoot: appRepoRoot,
    fromTag: fromTag,
    toRef: options.toRef,
  );

  // Dependent packages (packages/*) are, in this workspace, ALSO each their own
  // separate git repo — not a subdirectory of the outer workspace repo — so scanning
  // the outer repo here never actually finds real dependency commits (path/mention
  // matching against it only turns up unrelated pre-migration history). Worse, the
  // outer repo has no per-app tag history at all, so "since last release" for it was
  // unbounded: every run rescanned its ENTIRE commit history from the beginning,
  // producing the same large, unchanging "Workspace & Tooling" block on every single
  // changelog regardless of what actually changed. Skip it entirely for repos that
  // have their own git history — showing nothing is honest; showing the same stale
  // 200+ commits every time is not. (Proper per-dependency-repo scanning is a
  // separate, larger fix — each of the ~19 dependent packages would need its own
  // repo resolution, same as the target does above.)
  final outerCommits = targetHasOwnRepo ? <GitCommit>[] : targetCommits;

  print(
    '📜 Scanned ${targetCommits.length} commit(s) in ${target.name}\'s repository'
    '${targetHasOwnRepo ? ' (dependent-package/workspace commits skipped — see comment above)' : ''}.',
  );

  final packageCommits = <String, List<GitCommit>>{};
  final workspaceCommits = <GitCommit>[];
  final targetAliases = {
    target.name.toLowerCase(),
    target.relativePath.toLowerCase(),
    target.name.replaceAll('_', '').toLowerCase(),
  };

  if (targetHasOwnRepo) {
    // Every commit scanned from the target's own repo IS a target commit.
    packageCommits[target.name] = targetCommits;
  }

  for (final commit in outerCommits) {
    bool assigned = false;
    final subjectLower = commit.subject.toLowerCase();
    final bodyLower = commit.body.toLowerCase();

    // 1. Check if commit touches target app directory or mentions target app.
    // Skipped when the target has its own repo: its real commits were already
    // captured above, and outer-repo commits merely *mentioning* the app name
    // are unrelated history, not part of this release.
    if (!targetHasOwnRepo) {
      final touchesTarget = commit.changedFiles.any(
        (f) => isInPackage(f, target, workspacePackages.values),
      );
      final mentionsTarget = targetAliases.any(
        (a) => subjectLower.contains(a) || bodyLower.contains(a),
      );

      if (touchesTarget || mentionsTarget) {
        packageCommits.putIfAbsent(target.name, () => []).add(commit);
        assigned = true;
      }
    }

    // 2. Check if commit touches dependent packages
    for (final dep in internalDeps) {
      final touchesDep = commit.changedFiles.any(
        (f) => isInPackage(f, dep, workspacePackages.values),
      );
      final mentionsDep =
          subjectLower.contains(dep.name.toLowerCase()) ||
          subjectLower.contains(dep.relativePath.toLowerCase());
      if (touchesDep || mentionsDep) {
        packageCommits.putIfAbsent(dep.name, () => []).add(commit);
        assigned = true;
      }
    }

    // 3. Check if commit touches workspace tooling, root docs, or shared configuration
    if (!assigned) {
      final isOtherApp = commit.changedFiles.any(
        (f) => workspacePackages.values.any(
          (p) => p.name != target.name && isInPackage(f, p, workspacePackages.values),
        ),
      );
      final touchesTooling = commit.changedFiles.any(
        (f) =>
            f.startsWith('tooling/') ||
            f.startsWith('tool/') ||
            f.startsWith('docs/') ||
            f == 'pubspec.yaml' ||
            f == 'melos.yaml' ||
            f.endsWith('.sh') ||
            f.endsWith('.py'),
      );

      if (touchesTooling || (!isOtherApp && commit.changedFiles.isNotEmpty)) {
        workspaceCommits.add(commit);
      }
    }
  }

  var totalRelevantCommits =
      (packageCommits[target.name]?.length ?? 0) +
      internalDeps.fold<int>(
        0,
        (sum, dep) => sum + (packageCommits[dep.name]?.length ?? 0),
      ) +
      workspaceCommits.length;

  printCommitTable(
    commits: targetCommits,
    target: target,
    internalDeps: internalDeps,
    packageCommits: packageCommits,
    workspaceCommits: workspaceCommits,
    allPackages: workspacePackages.values,
    fromRef: fromTag,
    toRef: options.toRef,
  );

  print(
    '📝 Found $totalRelevantCommits relevant commits for ${target.name} across ${packageCommits.length} packages + tooling.',
  );

  final hasReleaseChanges = totalRelevantCommits > 0 || options.force;
  if (totalRelevantCommits == 0) {
    print(
      '⚠️ No commits found between ${fromTag ?? 'beginning'} and ${options.toRef}. Nothing new to release.',
    );
    if (options.mode == ReleaseMode.preview ||
        options.mode == ReleaseMode.changelog ||
        options.mode == ReleaseMode.commit) {
      exit(0);
    }
    print(
      '🏷️ Continuing with tag-only release for $tagName because Mode ${options.mode == ReleaseMode.push ? '5' : '4'} was requested.',
    );
  }

  // -------------------------------------------------------------
  // OPERATION: Pre-flight Verification Check (--verify)
  // -------------------------------------------------------------
  if (options.verify) {
    print('🩺 Running pre-flight verification (analyzer & tests)...');
    final analyzeRes = await Process.run('flutter', [
      'analyze',
      target.relativePath,
    ], workingDirectory: workspaceRoot);
    if (analyzeRes.exitCode != 0) {
      stderr.writeln(
        '❌ Verification failed: Static analysis errors found:\n${analyzeRes.stdout}',
      );
      exit(1);
    }
    print('✅ Pre-flight verification passed.');
  }

  // Generate formatted markdown changelog. Commit hashes link to GitHub when the
  // target's own repo remote resolves there (dependent-package/workspace commits
  // don't get links here since they may live in a different repo/remote).
  final githubCommitUrlPrefix = await resolveGithubCommitUrlPrefix(appRepoRoot);
  final compiledChangelog = buildCompiledChangelog(
    target: target,
    version: version,
    packageCommits: packageCommits,
    workspaceCommits: workspaceCommits,
    internalDeps: internalDeps,
    githubCommitUrlPrefix: githubCommitUrlPrefix,
  );

  print('\n══════════════════ GENERATED CHANGELOG PREVIEW ══════════════════');
  print(compiledChangelog);
  print('═════════════════════════════════════════════════════════════════\n');

  // -------------------------------------------------------------
  // OPERATION: Store Release Notes ("What's New")
  // -------------------------------------------------------------
  if (options.generateStoreNotes) {
    final storeNotes = buildStoreNotes(
      packageCommits[target.name] ?? [],
      version,
    );
    print('📱 ──────── STORE "WHAT\'S NEW" RELEASE NOTES ────────');
    print(storeNotes);
    print('───────────────────────────────────────────────────────\n');
    if (options.mode != ReleaseMode.preview) {
      await saveStoreNotes(workspaceRoot, target, storeNotes);
    }
  }

  // -------------------------------------------------------------
  // MODE 1: Preview Only
  // -------------------------------------------------------------
  if (options.mode == ReleaseMode.preview) {
    print(
      '✨ [MODE 1 - PREVIEW] Completed successfully. No files modified, no git changes.',
    );
    return;
  }

  // -------------------------------------------------------------
  // MODE 2+: Update CHANGELOG.md files
  // -------------------------------------------------------------
  if (hasReleaseChanges) {
    final targetChangelogFile = File(
      '$workspaceRoot/${target.relativePath}/CHANGELOG.md',
    );
    await prependToChangelog(targetChangelogFile, compiledChangelog);
    print('✅ Updated: ${target.relativePath}/CHANGELOG.md');

    for (final dep in internalDeps) {
      final commits = packageCommits[dep.name];
      if (commits != null && commits.isNotEmpty) {
        final pkgChangelog = buildPackageChangelog(dep, version, commits);
        final pkgChangelogFile = File(
          '$workspaceRoot/${dep.relativePath}/CHANGELOG.md',
        );
        await prependToChangelog(pkgChangelogFile, pkgChangelog);
        print('✅ Updated: ${dep.relativePath}/CHANGELOG.md');
      }
    }
  } else {
    print('ℹ️ Skipping changelog update because there are no new commits.');
  }

  if (options.mode == ReleaseMode.changelog) {
    print(
      '✨ [MODE 2 - CHANGELOG ONLY] Updated CHANGELOG.md files. No git commit or tag created.',
    );
    return;
  }

  // -------------------------------------------------------------
  // MODE 3+: Git Commit
  // -------------------------------------------------------------
  // When the target has its own repo, its CHANGELOG.md/pubspec.yaml must be added and
  // committed INSIDE that repo (paths relative to appRepoRoot, no "apps/<name>/" prefix —
  // that prefix only makes sense relative to the outer workspace repo). Any dependent
  // package changelogs (packages/*) still live in — and get committed to — the outer repo.
  var committedOuterDeps = false;
  if (!hasReleaseChanges) {
    print('ℹ️ Skipping release commit because there are no new commits.');
  } else if (targetHasOwnRepo) {
    await runGit(['add', 'CHANGELOG.md', 'pubspec.yaml'], appRepoRoot);
    final commitMsg = 'chore(release): release $tagName\n\n$compiledChangelog';
    final commitRes = await runGitWithMessageFile(
      ['commit', '-F'],
      commitMsg,
      appRepoRoot,
    );
    if (commitRes.exitCode == 0) {
      print(
        '✅ Git commit created in ${target.name}\'s repository: "chore(release): release $tagName"',
      );
    } else {
      print(
        'ℹ️ Git commit output (${target.name}): ${commitRes.stdout.toString().trim()} ${commitRes.stderr.toString().trim()}',
      );
    }

    final depFiles = [
      for (final dep in internalDeps)
        if (packageCommits.containsKey(dep.name))
          '${dep.relativePath}/CHANGELOG.md',
    ];
    if (depFiles.isNotEmpty) {
      await runGit(['add', ...depFiles], workspaceRoot);
      final depCommitRes = await runGit([
        'commit',
        '-m',
        'chore(release): update dependent package changelogs for $tagName',
      ], workspaceRoot);
      if (depCommitRes.exitCode == 0) {
        print(
          '✅ Git commit created in the workspace repository for dependent package changelogs.',
        );
        committedOuterDeps = true;
      }
    }
  } else {
    final filesToAdd = [
      '${target.relativePath}/CHANGELOG.md',
      '${target.relativePath}/pubspec.yaml',
      for (final dep in internalDeps)
        if (packageCommits.containsKey(dep.name))
          '${dep.relativePath}/CHANGELOG.md',
    ];
    await runGit(['add', ...filesToAdd], workspaceRoot);
    final commitMsg = 'chore(release): release $tagName\n\n$compiledChangelog';
    final commitRes = await runGitWithMessageFile(
      ['commit', '-F'],
      commitMsg,
      workspaceRoot,
    );
    if (commitRes.exitCode == 0) {
      print('✅ Git commit created: "chore(release): release $tagName"');
    } else {
      print(
        'ℹ️ Git commit output: ${commitRes.stdout.toString().trim()} ${commitRes.stderr.toString().trim()}',
      );
    }
  }

  if (options.mode == ReleaseMode.commit) {
    print(
      '✨ [MODE 3 - COMMIT] CHANGELOG.md files committed to local git branch. No tag created.',
    );
    return;
  }

  // -------------------------------------------------------------
  // MODE 4+: Create Annotated Git Tag (Local)
  // -------------------------------------------------------------
  // The app tag belongs to the target's own release history. The same release tag is
  // also applied to each dependent package repository that Melos resolved for this app.
  final tagArgs = ['tag', '-a', tagName, '-F'];
  if (options.force) {
    tagArgs.add('-f');
  }
  final releaseRepos = await resolveReleaseGitRoots(
    workspaceRoot: workspaceRoot,
    appRepoRoot: appRepoRoot,
    internalDeps: internalDeps,
  );
  final tagMessage = hasReleaseChanges
      ? 'Release $tagName\n\n$compiledChangelog'
      : 'Release $tagName\n\nNo code changes found since ${fromTag ?? 'the beginning'}; creating a version marker tag.';
  final tagFailures = <String>[];
  var tagCreatedCount = 0;
  var tagSkippedCount = 0;
  for (final repoRoot in releaseRepos) {
    final existingTag = await runGit(['tag', '-l', tagName], repoRoot);
    if (existingTag.stdout.toString().trim().isNotEmpty && !options.force) {
      tagSkippedCount += 1;
      print('ℹ️ Tag already exists in ${repoLabel(repoRoot)}: $tagName');
      continue;
    }

    final tagRes = await runGitWithMessageFile(tagArgs, tagMessage, repoRoot);
    if (tagRes.exitCode == 0) {
      tagCreatedCount += 1;
      print(
        '🏷️ Created local annotated Git tag in ${repoLabel(repoRoot)}: $tagName',
      );
    } else {
      tagFailures.add('${repoLabel(repoRoot)}: ${tagRes.stderr}');
    }
  }
  if (tagFailures.isNotEmpty) {
    stderr.writeln('❌ Error creating Git tag on some repositories:');
    for (final failure in tagFailures) {
      stderr.writeln('   - $failure');
    }
    exit(1);
  }
  print(
    '🏷️ Release tags processed across ${releaseRepos.length} repos ($tagCreatedCount created, $tagSkippedCount skipped).',
  );

  // -------------------------------------------------------------
  // OPERATION: Chat Webhook Notification (--notify)
  // -------------------------------------------------------------
  if (options.sendNotification) {
    await dispatchChatNotification(
      target.name,
      version,
      tagName,
      compiledChangelog,
    );
  }

  if (options.mode == ReleaseMode.tag) {
    await printReleaseSummary(tagName: tagName, repoRoot: appRepoRoot, pushed: false);
    print(
      '✨ [MODE 4 - LOCAL TAG] Created local Git tag: $tagName (No remote push).',
    );
    print(
      '👉 To push manually later: git push origin HEAD && git push origin $tagName',
    );
    return;
  }

  // -------------------------------------------------------------
  // MODE 5: Push to Remote
  // -------------------------------------------------------------
  print('🚀 Pushing commit & tag to remote repository...');
  final remoteRes = await runGit(['remote', 'get-url', 'origin'], appRepoRoot);
  if (remoteRes.exitCode != 0) {
    stderr.writeln('❌ No "origin" remote is configured in ${repoLabel(appRepoRoot)}. '
        'Add one (git remote add origin <url>) or use "Changelog + Commit + Local Git Tag" instead.');
    exit(1);
  }
  print('   Remote: origin → ${remoteRes.stdout.toString().trim()}');
  final pushCommitRes = await runGit(['push', 'origin', 'HEAD'], appRepoRoot);
  final pushProblems = <String>[];
  if (pushCommitRes.exitCode == 0) {
    print('✅ Pushed commit to remote (HEAD).');
  } else {
    pushProblems.add('commit push from ${repoLabel(appRepoRoot)}');
  }

  final pushTagFailures = <String>[];
  var pushedTagCount = 0;
  for (final repoRoot in releaseRepos) {
    final pushTagRes = await runGit(['push', 'origin', tagName], repoRoot);
    if (pushTagRes.exitCode == 0) {
      pushedTagCount += 1;
      print('✅ Pushed release tag ($tagName) from ${repoLabel(repoRoot)}.');
    } else {
      pushTagFailures.add('${repoLabel(repoRoot)}: ${pushTagRes.stderr}');
    }
  }
  if (pushTagFailures.isNotEmpty) {
    stderr.writeln('⚠️ Warning pushing tags on some repositories:');
    for (final failure in pushTagFailures) {
      stderr.writeln('   - $failure');
    }
  }
  print(
    '✅ Pushed release tag to $pushedTagCount/${releaseRepos.length} repositories.',
  );

  if (committedOuterDeps) {
    final pushDepsRes = await runGit(['push', 'origin', 'HEAD'], workspaceRoot);
    if (pushDepsRes.exitCode == 0) {
      print('✅ Pushed dependent package changelog commit (workspace repo).');
    } else {
      stderr.writeln(
        '⚠️ Warning pushing workspace repo commit: ${pushDepsRes.stderr}',
      );
    }
  }

  pushProblems.addAll(pushTagFailures.map((f) => 'tag push ${f.split(':').first}'));
  await printReleaseSummary(tagName: tagName, repoRoot: appRepoRoot, pushed: pushProblems.isEmpty);
  if (pushProblems.isNotEmpty) {
    stderr.writeln('❌ Release created locally, but pushing failed: ${pushProblems.join('; ')}. '
        'Check the git output above, then push manually: git push origin HEAD && git push origin $tagName');
    exit(1);
  }
  print(
    '\n🎉 [MODE 5 - FULL RELEASE] Release, changelog, commit, tag, and remote push complete!',
  );
}
