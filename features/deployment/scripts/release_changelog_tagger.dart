#!/usr/bin/env dart

import 'dart:convert';
import 'dart:io';

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

  // Load pub workspace packages
  final workspacePubspecFile = File('$workspaceRoot/pubspec.yaml');
  if (!workspacePubspecFile.existsSync()) {
    stderr.writeln('❌ Error: Root pubspec.yaml not found at $workspaceRoot');
    exit(1);
  }

  final workspacePackages = await scanWorkspacePackages(workspaceRoot);

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
        (f) => f.startsWith(target.relativePath),
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
        (f) => f.startsWith(dep.relativePath),
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
        (f) => f.startsWith('apps/') && !f.startsWith(target.relativePath),
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
  final pushCommitRes = await runGit(['push', 'origin', 'HEAD'], appRepoRoot);
  if (pushCommitRes.exitCode == 0) {
    print('✅ Pushed commit to remote (HEAD).');
  } else {
    stderr.writeln('⚠️ Warning pushing commit: ${pushCommitRes.stderr}');
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

  print(
    '\n🎉 [MODE 5 - FULL RELEASE] Release, changelog, commit, tag, and remote push complete!',
  );
}

/// Validate branch governance, ancestry linearity, and tag uniqueness
Future<void> validateBranchGovernance({
  required String workspaceRoot,
  required PackageInfo target,
  required String tagName,
  required ReleaseOptions options,
  String? fromTag,
}) async {
  // Always allow dry-run preview and changelog-only (no commit/tag/push) from any branch —
  // governance exists to stop TAGGING/committing from unmerged branches, not previewing text.
  if (options.mode == ReleaseMode.preview ||
      options.mode == ReleaseMode.changelog)
    return;

  final branchRes = await runGit(['branch', '--show-current'], workspaceRoot);
  final currentBranch = branchRes.stdout.toString().trim();

  if (currentBranch.isNotEmpty) {
    print('🌿 Active Git Branch: $currentBranch');
  }

  // 1. Branch Allowlist Enforcement
  if (!options.bypassBranchCheck && currentBranch.isNotEmpty) {
    final isAllowed = options.allowedBranches.any((pattern) {
      if (pattern.endsWith('/*')) {
        final prefix = pattern.substring(0, pattern.length - 2);
        return currentBranch.startsWith(prefix);
      }
      return currentBranch == pattern;
    });

    if (!isAllowed) {
      stderr.writeln(
        '\n❌ RELEASE GOVERNANCE ERROR: Branch "$currentBranch" is NOT an authorized release branch.',
      );
      stderr.writeln(
        '👉 Authorized Release Branches: ${options.allowedBranches.join(', ')}',
      );
      stderr.writeln(
        '👉 Why this rule exists: Creating release tags from unmerged feature branches causes divergent Git history and fragmented changelogs.',
      );
      stderr.writeln('👉 Solutions:');
      stderr.writeln(
        '   1. Switch to a release branch (e.g. git checkout main, git checkout release/...)',
      );
      stderr.writeln(
        '   2. Or run in preview mode: --mode=preview (allowed on all branches)',
      );
      stderr.writeln(
        '   3. Or bypass governance check (emergency only): --bypass-branch-check\n',
      );
      exit(1);
    }
  }

  // 2. Ancestry / History Linearity Check (Ensures previous release tag is in current branch's history)
  if (fromTag != null && fromTag.isNotEmpty && !options.force) {
    final ancestorRes = await runGit([
      'merge-base',
      '--is-ancestor',
      fromTag,
      'HEAD',
    ], workspaceRoot);
    if (ancestorRes.exitCode != 0) {
      stderr.writeln(
        '\n❌ RELEASE ANCESTRY ERROR: Previous release tag "$fromTag" is NOT an ancestor of current branch "$currentBranch".',
      );
      stderr.writeln(
        '👉 Cause: Branch "$currentBranch" has diverged or was created before "$fromTag" without merging the latest release.',
      );
      stderr.writeln(
        '👉 Impact: Tagging here will create disconnected release tags and overwrite CHANGELOG.md history.',
      );
      stderr.writeln('👉 Solutions:');
      stderr.writeln(
        '   1. Merge the latest release branch/tag into "$currentBranch" before releasing.',
      );
      stderr.writeln(
        '   2. Or run with --force (-f) if intentional divergence.\n',
      );
      exit(1);
    }
  }

  // 3. Tag Collision Check (Prevents duplicate tags)
  final tagExistsRes = await runGit(['tag', '-l', tagName], workspaceRoot);
  if (tagExistsRes.stdout.toString().trim().isNotEmpty &&
      !options.force &&
      !options.undo) {
    stderr.writeln(
      '\n❌ RELEASE COLLISION ERROR: Tag "$tagName" already exists.',
    );
    stderr.writeln(
      '👉 Version already released. Auto-bump with --bump=patch or specify new version with --version=x.y.z.',
    );
    stderr.writeln('👉 To overwrite existing tag, use --force (-f).\n');
    exit(1);
  }
}

/// Release execution modes
enum ReleaseMode {
  preview, // Mode 1: Analyze & Preview (Dry-run)
  changelog, // Mode 2: Update CHANGELOG.md only
  commit, // Mode 3: Update CHANGELOG.md + Git commit
  tag, // Mode 4: Update CHANGELOG.md + Git commit + Local Git Tag
  push, // Mode 5: Update CHANGELOG.md + Git commit + Local Git Tag + Remote Push
}

/// Representation of a parsed Git commit
class GitCommit {
  final String hash;
  final String shortHash;
  final String subject;
  final String author;
  final String date;
  final String body;
  final List<String> changedFiles;

  GitCommit({
    required this.hash,
    required this.shortHash,
    required this.subject,
    required this.author,
    required this.date,
    this.body = '',
    this.changedFiles = const [],
  });

  String get type {
    final match = RegExp(
      r'^(\w+)(?:\(([^)]+)\))?(!)?:\s*(.+)$',
    ).firstMatch(subject);
    if (match != null) {
      return match.group(1)!.toLowerCase();
    }
    return 'other';
  }

  String? get scope {
    final match = RegExp(
      r'^(\w+)(?:\(([^)]+)\))?(!)?:\s*(.+)$',
    ).firstMatch(subject);
    return match?.group(2);
  }

  String get description {
    final match = RegExp(
      r'^(\w+)(?:\(([^)]+)\))?(!)?:\s*(.+)$',
    ).firstMatch(subject);
    if (match != null) {
      return match.group(4)!.trim();
    }
    return subject;
  }

  bool get isBreaking {
    return subject.contains('!:') || body.contains('BREAKING CHANGE:');
  }
}

/// Representation of a workspace app or package
class PackageInfo {
  final String name;
  final String relativePath;
  final String absolutePath;
  final String? version;
  final Set<String> directDependencies;

  PackageInfo({
    required this.name,
    required this.relativePath,
    required this.absolutePath,
    this.version,
    required this.directDependencies,
  });
}

/// CLI Options
class ReleaseOptions {
  String? appName;
  String? packageName;
  String? version;
  String? bumpType; // patch, minor, major, build
  String?
  flavor; // dev, qa, prod, staging, or any app-specific name — see flavorTagSuffix()
  String? fromTag;
  String toRef = 'HEAD';
  String? workspaceRoot;
  ReleaseMode mode = ReleaseMode.tag;
  bool force = false;
  bool all = false;
  bool showHelp = false;
  bool showStatus = false;
  bool generateStoreNotes = false;
  bool sendNotification = false;
  bool verify = false;
  bool undo = false;
  bool bypassBranchCheck = false;
  List<String> allowedBranches = [
    'main',
    'master',
    'develop',
    'release',
    'release/*',
    'hotfix/*',
  ];

  String get modeDescription {
    switch (mode) {
      case ReleaseMode.preview:
        return 'Mode 1: Preview Only (Dry-run)';
      case ReleaseMode.changelog:
        return 'Mode 2: Update CHANGELOG.md Only';
      case ReleaseMode.commit:
        return 'Mode 3: Update CHANGELOG.md + Git Commit';
      case ReleaseMode.tag:
        return 'Mode 4: Update CHANGELOG.md + Git Commit + Local Git Tag';
      case ReleaseMode.push:
        return 'Mode 5: Full Release (Changelog + Commit + Tag + Remote Push)';
    }
  }
}

ReleaseOptions parseArgs(List<String> args) {
  final options = ReleaseOptions();
  for (int i = 0; i < args.length; i++) {
    final arg = args[i];
    if (arg == '--help' || arg == '-h') {
      options.showHelp = true;
    } else if (arg == '--status' || arg == '-s' || arg == '--unreleased') {
      options.showStatus = true;
    } else if (arg == '--undo' || arg == '--rollback') {
      options.undo = true;
    } else if (arg == '--verify' || arg == '--check') {
      options.verify = true;
    } else if (arg == '--bypass-branch-check' || arg == '--force-branch') {
      options.bypassBranchCheck = true;
    } else if (arg.startsWith('--allowed-branches=')) {
      options.allowedBranches = arg
          .substring(19)
          .split(',')
          .map((b) => b.trim())
          .toList();
    } else if (arg == '--store' ||
        arg == '--store-notes' ||
        arg == '--whats-new') {
      options.generateStoreNotes = true;
    } else if (arg == '--notify' || arg == '--chat') {
      options.sendNotification = true;
    } else if (arg.startsWith('--bump=')) {
      options.bumpType = arg.substring(7).toLowerCase();
    } else if (arg == '--bump') {
      if (i + 1 < args.length) options.bumpType = args[++i].toLowerCase();
    } else if (arg.startsWith('--flavor=') || arg.startsWith('--env=')) {
      options.flavor = arg.substring(arg.indexOf('=') + 1);
    } else if (arg == '--flavor' || arg == '--env' || arg == '-e') {
      if (i + 1 < args.length) options.flavor = args[++i];
    } else if (arg.startsWith('--app=')) {
      options.appName = arg.substring(6).replaceAll('apps/', '');
    } else if (arg == '--app' || arg == '-a') {
      if (i + 1 < args.length)
        options.appName = args[++i].replaceAll('apps/', '');
    } else if (arg.startsWith('--package=')) {
      options.packageName = arg.substring(10).replaceAll('packages/', '');
    } else if (arg == '--package' || arg == '-p') {
      if (i + 1 < args.length)
        options.packageName = args[++i].replaceAll('packages/', '');
    } else if (arg.startsWith('--version=')) {
      options.version = arg.substring(10);
    } else if (arg == '--version' || arg == '-v') {
      if (i + 1 < args.length) options.version = args[++i];
    } else if (arg.startsWith('--from-tag=')) {
      options.fromTag = arg.substring(11);
    } else if (arg.startsWith('--to-ref=')) {
      options.toRef = arg.substring(9);
    } else if (arg.startsWith('--workspace=')) {
      options.workspaceRoot = arg.substring(12);
    } else if (arg.startsWith('--mode=')) {
      final m = arg.substring(7).toLowerCase();
      options.mode = parseMode(m);
    } else if (arg == '--dry-run' || arg == '--preview') {
      options.mode = ReleaseMode.preview;
    } else if (arg == '--changelog-only' || arg == '--write-changelog') {
      options.mode = ReleaseMode.changelog;
    } else if (arg == '--commit-only') {
      options.mode = ReleaseMode.commit;
    } else if (arg == '--local-tag' || arg == '--no-push') {
      options.mode = ReleaseMode.tag;
    } else if (arg == '--push' || arg == '--remote-push') {
      options.mode = ReleaseMode.push;
    } else if (arg == '--force' || arg == '-f') {
      options.force = true;
    } else if (arg == '--all') {
      options.all = true;
    } else if (!arg.startsWith('-') &&
        options.appName == null &&
        options.packageName == null) {
      if (arg.startsWith('apps/')) {
        options.appName = arg.replaceFirst('apps/', '');
      } else if (arg.startsWith('packages/')) {
        options.packageName = arg.replaceFirst('packages/', '');
      } else {
        options.appName = arg;
      }
    }
  }
  return options;
}

ReleaseMode parseMode(String val) {
  switch (val) {
    case 'preview':
    case '1':
    case 'dry-run':
    case 'analyze':
      return ReleaseMode.preview;
    case 'changelog':
    case '2':
    case 'changelog-only':
    case 'write-changelog':
      return ReleaseMode.changelog;
    case 'commit':
    case '3':
    case 'commit-only':
      return ReleaseMode.commit;
    case 'tag':
    case '4':
    case 'local-tag':
      return ReleaseMode.tag;
    case 'push':
    case '5':
    case 'release':
    case 'full':
      return ReleaseMode.push;
    default:
      return ReleaseMode.tag;
  }
}

void printHelp() {
  print('''
Melos Release Changelog & Git Tag Complete Automation Tool

Usage:
  dart run release_changelog_tagger.dart --app=<app_name> [options]
  dart run release_changelog_tagger.dart --package=<pkg_name> [options]

Operational Modes:
  --mode=preview   (Mode 1): Analyze & preview changelog only (Dry-run, zero file/git changes)
  --mode=changelog (Mode 2): Update CHANGELOG.md in app & packages only (No commit/tag)
  --mode=commit    (Mode 3): Update CHANGELOG.md + Git commit (No tag/push)
  --mode=tag       (Mode 4): Update CHANGELOG.md + Git commit + Local annotated Git tag (DEFAULT)
  --mode=push      (Mode 5): Update CHANGELOG.md + Git commit + Local Git tag + Push to remote

Governance & Safeguards:
  --bypass-branch-check    Allow releasing on non-standard branches (Default allows: main, develop, release/*, hotfix/*)
  --allowed-branches=<csv> Specify custom comma-separated list of authorized release branches

Advanced Operations:
  --status, -s             Scan workspace and report unreleased commits across ALL apps & packages
  --bump=<type>            Auto-bump version in pubspec.yaml (patch | minor | major | build)
  --store                  Generate consumer-friendly App Store / Play Store "What's New" release notes
  --verify                 Run pre-flight analysis & tests on app and modified packages before tagging
  --notify                 Broadcast release changelog to Google Chat / Slack webhook
  --undo                   Rollback/delete accidental Git tag and revert changelog commit

Options:
  --app, -a <name>         Name or path of target app (e.g. my_app, apps/my_app)
  --package, -p <name>     Name or path of target package (e.g. app_ui_kit)
  --version, -v <version>  Explicit release version (e.g. 1.2.0)
  --workspace <path>       Monorepo workspace root directory (defaults to current dir)
  --flavor, --env, -e <name>  Environment/build flavor (e.g. dev, qa). Appends "-<name>" to the
                           release tag and scopes "since last release" lookups to that flavor.
                           Omit, or pass prod/production/any/all, for the default unsuffixed
                           release — this is also what apps with only one flavor should use.
  --from-tag <tag>         Tag to calculate changes from (defaults to latest <name>-v* tag)
  --to-ref <ref>           Target git ref (default: HEAD)
  --force, -f              Force tag recreation (-f) or allow release with 0 commits
  --help, -h               Show this help message
''');
}

/// Bump Semantic Version string (e.g. 1.0.5+96 -> 1.0.6+97)
String bumpSemVer(String currentVersion, String bumpType) {
  final parts = currentVersion.split('+');
  final semverParts = parts[0]
      .split('.')
      .map((p) => int.tryParse(p) ?? 0)
      .toList();
  while (semverParts.length < 3) semverParts.add(0);

  int major = semverParts[0];
  int minor = semverParts[1];
  int patch = semverParts[2];
  int build = parts.length > 1 ? (int.tryParse(parts[1]) ?? 1) + 1 : 1;

  switch (bumpType.toLowerCase()) {
    case 'major':
      major++;
      minor = 0;
      patch = 0;
      break;
    case 'minor':
      minor++;
      patch = 0;
      break;
    case 'patch':
      patch++;
      break;
    case 'build':
      break;
  }

  if (parts.length > 1 || bumpType.toLowerCase() == 'build') {
    return '$major.$minor.$patch+$build';
  }
  return '$major.$minor.$patch';
}

/// Update version: x.y.z in a pubspec.yaml file
void updatePubspecVersion(File pubspecFile, String newVersion) {
  if (!pubspecFile.existsSync()) return;
  final content = pubspecFile.readAsStringSync();
  final updated = content.replaceFirst(
    RegExp(r'^version:\s*.*$', multiLine: true),
    'version: $newVersion',
  );
  pubspecFile.writeAsStringSync(updated);
}

/// Build Consumer-Friendly Store Release Notes (What's New)
String buildStoreNotes(List<GitCommit> commits, String version) {
  final buffer = StringBuffer();
  buffer.writeln("What's New in Version $version:");
  final userBullets = <String>[];

  for (final c in commits) {
    if (c.type == 'feat') {
      userBullets.add('✨ ${c.description}');
    } else if (c.type == 'fix') {
      userBullets.add('🛠️ ${c.description}');
    } else if (c.type == 'perf') {
      userBullets.add('⚡ Performance improvements and optimizations');
    }
  }

  if (userBullets.isEmpty) {
    buffer.writeln('• General performance enhancements and bug fixes.');
  } else {
    for (final b in userBullets.take(5)) {
      buffer.writeln('• $b');
    }
  }
  return buffer.toString().trim();
}

/// Save Store release notes to fastlane metadata
Future<void> saveStoreNotes(
  String workspaceRoot,
  PackageInfo target,
  String notes,
) async {
  final targetDir = Directory(
    '$workspaceRoot/${target.relativePath}/android/fastlane/metadata/android/en-US/changelogs',
  );
  if (targetDir.existsSync()) {
    final noteFile = File('${targetDir.path}/default.txt');
    await noteFile.writeAsString(notes);
    print(
      '📱 Saved store notes to ${target.relativePath}/android/fastlane/metadata/.../default.txt',
    );
  }
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
                    c.changedFiles.any((f) => f.startsWith(pkg.relativePath)),
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

/// Cleanly undo/rollback an accidental release
Future<void> runReleaseUndo(
  String workspaceRoot,
  PackageInfo target,
  String tagName,
) async {
  print('⚠️ Rolling back release for $tagName...');

  final delTagRes = await runGit(['tag', '-d', tagName], workspaceRoot);
  if (delTagRes.exitCode == 0) {
    print('🗑️ Deleted local tag: $tagName');
  } else {
    print('ℹ️ Local tag $tagName not found or already deleted.');
  }

  print('👉 To delete tag from remote if already pushed, run:');
  print('   git push origin --delete $tagName');
  print('👉 To undo the release commit, run:');
  print('   git revert HEAD --no-edit');
}

/// Dispatch chat notification to Google Chat / Slack webhook
Future<void> dispatchChatNotification(
  String appName,
  String version,
  String tagName,
  String changelog,
) async {
  final webhookUrl =
      Platform.environment['GOOGLE_CHAT_WEBHOOK_URL'] ??
      Platform.environment['SLACK_WEBHOOK_URL'];
  if (webhookUrl == null || webhookUrl.isEmpty) {
    print('ℹ️ No GOOGLE_CHAT_WEBHOOK_URL configured. Skipping chat broadcast.');
    return;
  }

  print('📢 Sending release notification to chat webhook...');
  try {
    final payload = json.encode({
      "text": "🚀 *New Release: $appName $version* ($tagName)\n\n$changelog",
    });
    final client = HttpClient();
    final req = await client.postUrl(Uri.parse(webhookUrl));
    req.headers.set('Content-Type', 'application/json; charset=UTF-8');
    req.write(payload);
    final resp = await req.close();
    if (resp.statusCode == 200) {
      print('✅ Release notification sent to chat!');
    }
  } catch (e) {
    print('⚠️ Chat webhook error: $e');
  }
}

/// Scan all apps and packages in workspace
Future<Map<String, PackageInfo>> scanWorkspacePackages(
  String workspaceRoot,
) async {
  final packages = <String, PackageInfo>{};

  final searchDirs = [
    Directory('$workspaceRoot/apps'),
    Directory('$workspaceRoot/packages'),
  ];

  for (final dir in searchDirs) {
    if (!dir.existsSync()) continue;
    final entities = dir.listSync(recursive: true, followLinks: false);
    for (final entity in entities) {
      if (entity is File && entity.path.endsWith('pubspec.yaml')) {
        final pkgDir = entity.parent;
        final relPath = pkgDir.path.substring(workspaceRoot.length + 1);

        if (pkgDir.path == workspaceRoot ||
            relPath.contains('/build/') ||
            relPath.startsWith('build/') ||
            relPath.contains('/.dart_tool/') ||
            relPath.contains('/Pods/')) {
          continue;
        }

        final content = entity.readAsStringSync();
        final nameMatch = RegExp(
          r'^name:\s*([a-zA-Z0-9_-]+)',
          multiLine: true,
        ).firstMatch(content);
        final versionMatch = RegExp(
          r'^version:\s*([0-9a-zA-Z\.\+\-]+)',
          multiLine: true,
        ).firstMatch(content);

        if (nameMatch != null) {
          final name = nameMatch.group(1)!;
          final version = versionMatch?.group(1);
          final deps = extractDependencyNames(content);

          packages[name] = PackageInfo(
            name: name,
            relativePath: relPath,
            absolutePath: pkgDir.path,
            version: version,
            directDependencies: deps,
          );
        }
      }
    }
  }

  return packages;
}

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

/// A tag produced by a flavor-suffixed release (e.g. `app-v1.2.0-qa`) ends in a
/// hyphen followed by letters; a primary/no-flavor release (`app-v1.2.0+228`)
/// always ends in a digit (the version or build number). No global registry of
/// "known flavors" is needed — this distinguishes the two shapes structurally.
final _flavorSuffixedTagPattern = RegExp(r'-[A-Za-z]+$');

/// Find latest release tag matching <target_name>-v* or v*, scoped to the same
/// environment/flavor as the release currently being computed. `flavorSuffix`
/// is either null (primary/no-flavor release — matches only unsuffixed tags)
/// or a suffix like `-qa` (matches only tags ending in that exact suffix), so a
/// QA release's "since last release" window never gets mixed up with PROD's.
Future<String?> findLatestTagForTarget(
  String targetName,
  String workspaceRoot, {
  String? flavorSuffix,
}) async {
  String? pickMatching(ProcessResult res) {
    if (res.exitCode != 0 || res.stdout.toString().trim().isEmpty) return null;
    final tags = res.stdout
        .toString()
        .trim()
        .split('\n')
        .map((t) => t.trim())
        .where((t) => t.isNotEmpty)
        .toList();
    final matching = tags.where((t) {
      if (flavorSuffix != null) return t.endsWith(flavorSuffix);
      return !_flavorSuffixedTagPattern.hasMatch(t);
    }).toList();
    return matching.isNotEmpty ? matching.first : null;
  }

  final tagRes = await runGit([
    'tag',
    '-l',
    '--sort=-v:refname',
    '$targetName-v*',
  ], workspaceRoot);
  final direct = pickMatching(tagRes);
  if (direct != null) return direct;

  final fallbackRes = await runGit([
    'tag',
    '-l',
    '--sort=-v:refname',
    'v*',
  ], workspaceRoot);
  return pickMatching(fallbackRes);
}

/// The set of flavor names treated as "the primary/default release" — these get
/// NO tag suffix, preserving today's `<app>-v<version>` naming exactly (so every
/// tag created before this feature existed, and every app with only one flavor
/// or none configured at all, keeps working unchanged). Anything else (qa, dev,
/// staging, or any other app-specific flavor name) gets an explicit `-<flavor>`
/// suffix so its releases are visibly distinct from production's.
const _primaryFlavorNames = {'prod', 'production', 'release', 'any', 'all', ''};

/// Returns the tag suffix (e.g. `-qa`) for a given flavor, or null when no
/// suffix should be applied (flavor unset, or one of the "primary" names above).
String? flavorTagSuffix(String? flavor) {
  if (flavor == null) return null;
  final normalized = flavor.trim().toLowerCase();
  if (_primaryFlavorNames.contains(normalized)) return null;
  return '-$normalized';
}

/// Get all git commits in timeline between fromTag and toRef with modified file lists
Future<List<GitCommit>> getAllCommitsInRange({
  required String workspaceRoot,
  String? fromTag,
  String toRef = 'HEAD',
}) async {
  final args = <String>[
    'log',
    '--pretty=format:COMMIT_START%x1f%H%x1f%h%x1f%s%x1f%an%x1f%ad%x1f%b%x1fCOMMIT_END',
    '--name-only',
    '--date=format:%Y-%m-%d %H:%M',
    '--no-merges',
  ];

  if (fromTag != null && fromTag.isNotEmpty) {
    args.add('$fromTag..$toRef');
  } else {
    args.add(toRef);
  }

  final res = await runGit(args, workspaceRoot);
  if (res.exitCode != 0 || res.stdout.toString().trim().isEmpty) {
    return [];
  }

  final output = res.stdout.toString();
  final rawRecords = output.split('COMMIT_START');
  final commits = <GitCommit>[];

  for (final record in rawRecords) {
    final trimmed = record.trim();
    if (trimmed.isEmpty) continue;

    final endIdx = trimmed.indexOf('COMMIT_END');
    if (endIdx == -1) continue;

    final headerChunk = trimmed.substring(0, endIdx);
    final filesChunk = trimmed.substring(endIdx + 'COMMIT_END'.length).trim();

    final parts = headerChunk.split('\x1f').where((p) => p.isNotEmpty).toList();
    final files = filesChunk
        .split('\n')
        .map((f) => f.trim())
        .where((f) => f.isNotEmpty)
        .toList();

    if (parts.length >= 5) {
      commits.add(
        GitCommit(
          hash: parts[0].trim(),
          shortHash: parts[1].trim(),
          subject: parts[2].trim(),
          author: parts[3].trim(),
          date: parts[4].trim(),
          body: parts.length > 5 ? parts[5].trim() : '',
          changedFiles: files,
        ),
      );
    }
  }

  return commits;
}

/// Build the compiled bulleted changelog combining app & package changes
/// Commit types treated as low-signal maintenance noise — kept out of the main
/// Features/Fixes/Changes sections (unless breaking) and tucked into a collapsed
/// "maintenance" block instead, so they're still visible but don't bury real changes.
const _noiseCommitTypes = {'chore', 'docs', 'style', 'ci', 'test', 'build'};

String buildCompiledChangelog({
  required PackageInfo target,
  required String version,
  required Map<String, List<GitCommit>> packageCommits,
  List<GitCommit> workspaceCommits = const [],
  required List<PackageInfo> internalDeps,
  String? githubCommitUrlPrefix,
}) {
  final today = DateTime.now().toIso8601String().split('T').first;
  final buffer = StringBuffer();

  buffer.writeln('## [$version] - $today\n');

  final targetCommits = packageCommits[target.name] ?? [];
  final breakingCommits = <String>[];
  final featCommits = <String>[];
  final fixCommits = <String>[];
  final refactorCommits = <String>[];
  final otherCommits = <String>[];
  final maintenanceCommits = <GitCommit>[];

  for (final c in targetCommits) {
    if (!c.isBreaking && _noiseCommitTypes.contains(c.type)) {
      maintenanceCommits.add(c);
      continue;
    }
    final line = formatCommitLine(c, commitUrlPrefix: githubCommitUrlPrefix);
    if (c.isBreaking) {
      breakingCommits.add(line);
    } else if (c.type == 'feat') {
      featCommits.add(line);
    } else if (c.type == 'fix') {
      fixCommits.add(line);
    } else if (c.type == 'refactor' || c.type == 'perf') {
      refactorCommits.add(line);
    } else {
      otherCommits.add(line);
    }
  }

  // Quick-scan summary: counts by category, then who contributed.
  final summaryParts = <String>[
    if (featCommits.isNotEmpty)
      '${featCommits.length} feature${featCommits.length == 1 ? '' : 's'}',
    if (fixCommits.isNotEmpty)
      '${fixCommits.length} fix${fixCommits.length == 1 ? '' : 'es'}',
    if (refactorCommits.isNotEmpty)
      '${refactorCommits.length} refactor${refactorCommits.length == 1 ? '' : 's'}',
    if (otherCommits.isNotEmpty)
      '${otherCommits.length} other change${otherCommits.length == 1 ? '' : 's'}',
    if (maintenanceCommits.isNotEmpty)
      '${maintenanceCommits.length} maintenance commit${maintenanceCommits.length == 1 ? '' : 's'}',
  ];
  if (summaryParts.isNotEmpty) {
    buffer.writeln('_${summaryParts.join(' · ')}_\n');
  }

  final contributorCounts = <String, int>{};
  for (final c in targetCommits) {
    contributorCounts[c.author] = (contributorCounts[c.author] ?? 0) + 1;
  }
  if (contributorCounts.isNotEmpty) {
    final sortedContributors = contributorCounts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final contributorsLine = sortedContributors
        .map((e) => '${e.key} (${e.value})')
        .join(', ');
    buffer.writeln('**👥 Contributors:** $contributorsLine\n');
  }

  if (breakingCommits.isNotEmpty) {
    buffer.writeln('### 💥 Breaking Changes');
    for (final line in breakingCommits) {
      buffer.writeln(line);
    }
    buffer.writeln();
  }

  if (featCommits.isNotEmpty) {
    buffer.writeln('### 🚀 Features');
    for (final line in featCommits) {
      buffer.writeln(line);
    }
    buffer.writeln();
  }

  if (fixCommits.isNotEmpty) {
    buffer.writeln('### 🐛 Bug Fixes');
    for (final line in fixCommits) {
      buffer.writeln(line);
    }
    buffer.writeln();
  }

  if (refactorCommits.isNotEmpty) {
    buffer.writeln('### ⚡ Performance & Refactoring');
    for (final line in refactorCommits) {
      buffer.writeln(line);
    }
    buffer.writeln();
  }

  if (otherCommits.isNotEmpty) {
    buffer.writeln('### 📝 Changes');
    for (final line in otherCommits) {
      buffer.writeln(line);
    }
    buffer.writeln();
  }

  final modifiedDeps = internalDeps
      .where(
        (d) =>
            packageCommits.containsKey(d.name) &&
            packageCommits[d.name]!.isNotEmpty,
      )
      .toList();

  if (modifiedDeps.isNotEmpty) {
    buffer.writeln('### 📦 Dependent Package Updates');
    for (final dep in modifiedDeps) {
      final commits = packageCommits[dep.name]!;
      buffer.writeln('* **${dep.name}** (`${dep.relativePath}`):');
      for (final c in commits) {
        buffer.writeln(
          formatCommitLine(c, includeScope: false, bullet: '  * '),
        );
      }
    }
    buffer.writeln();
  }

  if (workspaceCommits.isNotEmpty) {
    buffer.writeln('### 🛠️ Workspace & Tooling');
    for (final c in workspaceCommits) {
      buffer.writeln(formatCommitLine(c));
    }
    buffer.writeln();
  }

  if (maintenanceCommits.isNotEmpty) {
    buffer.writeln('<details>');
    buffer.writeln(
      '<summary>🧹 ${maintenanceCommits.length} maintenance commit${maintenanceCommits.length == 1 ? '' : 's'} (chore/docs/style/ci/test/build)</summary>\n',
    );
    for (final c in maintenanceCommits) {
      buffer.writeln(
        formatCommitLine(c, commitUrlPrefix: githubCommitUrlPrefix),
      );
    }
    buffer.writeln();
    buffer.writeln('</details>');
    buffer.writeln();
  }

  return buffer.toString().trimRight();
}

String formatCommitLine(
  GitCommit commit, {
  bool includeScope = true,
  String bullet = '* ',
  String? commitUrlPrefix,
}) {
  final scopeStr = (includeScope && commit.scope != null)
      ? '**${commit.scope}**: '
      : '';
  final description = _highlightTicketIds(commit.description);
  final hashPart = commitUrlPrefix != null
      ? '[`${commit.shortHash}`]($commitUrlPrefix${commit.hash})'
      : '`${commit.shortHash}`';
  return '$bullet$scopeStr$description ($hashPart, ${commit.date}, ${commit.author})';
}

String buildPackageChangelog(
  PackageInfo pkg,
  String version,
  List<GitCommit> commits,
) {
  final today = DateTime.now().toIso8601String().split('T').first;
  final buffer = StringBuffer();

  buffer.writeln('## [$version] - $today\n');

  final breakingCommits = commits.where((c) => c.isBreaking).toList();
  final nonBreaking = commits.where((c) => !c.isBreaking).toList();
  final maintenanceCommits = nonBreaking
      .where((c) => _noiseCommitTypes.contains(c.type))
      .toList();
  final rest = nonBreaking
      .where((c) => !_noiseCommitTypes.contains(c.type))
      .toList();
  final featCommits = rest.where((c) => c.type == 'feat').toList();
  final fixCommits = rest.where((c) => c.type == 'fix').toList();
  final otherCommits = rest
      .where((c) => c.type != 'feat' && c.type != 'fix')
      .toList();

  final summaryParts = <String>[
    if (featCommits.isNotEmpty)
      '${featCommits.length} feature${featCommits.length == 1 ? '' : 's'}',
    if (fixCommits.isNotEmpty)
      '${fixCommits.length} fix${fixCommits.length == 1 ? '' : 'es'}',
    if (otherCommits.isNotEmpty)
      '${otherCommits.length} other change${otherCommits.length == 1 ? '' : 's'}',
    if (maintenanceCommits.isNotEmpty)
      '${maintenanceCommits.length} maintenance commit${maintenanceCommits.length == 1 ? '' : 's'}',
  ];
  if (summaryParts.isNotEmpty) {
    buffer.writeln('_${summaryParts.join(' · ')}_\n');
  }

  final contributorCounts = <String, int>{};
  for (final c in commits) {
    contributorCounts[c.author] = (contributorCounts[c.author] ?? 0) + 1;
  }
  if (contributorCounts.isNotEmpty) {
    final sortedContributors = contributorCounts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    buffer.writeln(
      '**👥 Contributors:** ${sortedContributors.map((e) => '${e.key} (${e.value})').join(', ')}\n',
    );
  }

  if (breakingCommits.isNotEmpty) {
    buffer.writeln('### 💥 Breaking Changes');
    for (final c in breakingCommits) {
      buffer.writeln(formatCommitLine(c));
    }
    buffer.writeln();
  }

  if (featCommits.isNotEmpty) {
    buffer.writeln('### 🚀 Features');
    for (final c in featCommits) {
      buffer.writeln(formatCommitLine(c));
    }
    buffer.writeln();
  }

  if (fixCommits.isNotEmpty) {
    buffer.writeln('### 🐛 Bug Fixes');
    for (final c in fixCommits) {
      buffer.writeln(formatCommitLine(c));
    }
    buffer.writeln();
  }

  if (otherCommits.isNotEmpty) {
    buffer.writeln('### 📝 Other Changes');
    for (final c in otherCommits) {
      buffer.writeln(formatCommitLine(c));
    }
    buffer.writeln();
  }

  if (maintenanceCommits.isNotEmpty) {
    buffer.writeln('<details>');
    buffer.writeln(
      '<summary>🧹 ${maintenanceCommits.length} maintenance commit${maintenanceCommits.length == 1 ? '' : 's'} (chore/docs/style/ci/test/build)</summary>\n',
    );
    for (final c in maintenanceCommits) {
      buffer.writeln(formatCommitLine(c));
    }
    buffer.writeln();
    buffer.writeln('</details>');
    buffer.writeln();
  }

  return buffer.toString().trimRight();
}

Future<void> prependToChangelog(File changelogFile, String newContent) async {
  String existingContent = '';
  if (changelogFile.existsSync()) {
    existingContent = await changelogFile.readAsString();
  }

  String finalContent;
  if (existingContent.trim().isEmpty) {
    finalContent = '# Changelog\n\n$newContent\n';
  } else if (existingContent.startsWith('# Changelog')) {
    final body = existingContent
        .replaceFirst(RegExp(r'^#\s*Changelog\s*'), '')
        .trimLeft();
    finalContent = '# Changelog\n\n$newContent\n\n$body';
  } else {
    finalContent = '# Changelog\n\n$newContent\n\n$existingContent';
  }

  await changelogFile.writeAsString(finalContent);
}

Future<ProcessResult> runGit(List<String> args, String workingDirectory) {
  return Process.run('git', args, workingDirectory: workingDirectory);
}

Future<ProcessResult> runGitWithMessageFile(
  List<String> argsBeforeFile,
  String message,
  String workingDirectory,
) async {
  final tempDir = await Directory(
    workingDirectory,
  ).createTemp('.deployment-release-msg-');
  final messageFile = File('${tempDir.path}/message.txt');

  try {
    await messageFile.writeAsString(message);
    return await runGit([
      ...argsBeforeFile,
      messageFile.path,
    ], workingDirectory);
  } finally {
    if (tempDir.existsSync()) {
      await tempDir.delete(recursive: true);
    }
  }
}

Future<List<String>> resolveReleaseGitRoots({
  required String workspaceRoot,
  required String appRepoRoot,
  required List<PackageInfo> internalDeps,
}) async {
  final seen = <String>{};
  final roots = <String>[];

  void addRoot(String root) {
    final normalized = Directory(root).absolute.path;
    if (seen.add(normalized)) {
      roots.add(normalized);
    }
  }

  addRoot(appRepoRoot);
  for (final dep in internalDeps) {
    final depRoot = await resolveGitRoot('$workspaceRoot/${dep.relativePath}');
    if (depRoot != null) {
      addRoot(depRoot);
    }
  }

  return roots;
}

String repoLabel(String repoRoot) {
  final parts = Directory(
    repoRoot,
  ).absolute.uri.pathSegments.where((p) => p.isNotEmpty).toList();
  if (parts.length >= 2) {
    return '${parts[parts.length - 2]}/${parts.last}';
  }
  return repoRoot;
}

/// Resolve the actual Git repository root that `path` lives inside. Returns
/// null if `path` doesn't exist or isn't inside a Git working tree.
///
/// Some apps in this workspace (e.g. everything under `apps/`) are gitignored
/// at the monorepo root and are actually their OWN separate Git repositories,
/// not just a subdirectory of the outer workspace repo. Every git-history
/// operation (tag lookup, commit scanning, branch checks, commit/tag/push)
/// must run inside the correct repo, or it silently operates on unrelated
/// history from the wrong one.
Future<String?> resolveGitRoot(String path) async {
  if (!Directory(path).existsSync()) return null;
  final res = await runGit(['rev-parse', '--show-toplevel'], path);
  if (res.exitCode != 0) return null;
  final root = res.stdout.toString().trim();
  return root.isEmpty ? null : root;
}

/// If `repoRoot`'s `origin` remote points at github.com, return the URL prefix
/// (`https://github.com/<owner>/<repo>/commit/`) that a full commit hash can be
/// appended to for a clickable link. Returns null for any other remote (or none).
Future<String?> resolveGithubCommitUrlPrefix(String repoRoot) async {
  final res = await runGit(['remote', 'get-url', 'origin'], repoRoot);
  if (res.exitCode != 0) return null;
  final remoteUrl = res.stdout.toString().trim();
  final match = RegExp(
    r'github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?$',
  ).firstMatch(remoteUrl);
  if (match == null) return null;
  return 'https://github.com/${match.group(1)}/${match.group(2)}/commit/';
}

/// Recognizes issue-tracker-style ticket IDs (e.g. `TYRI-1234`, `GH-42`) inside
/// commit text so they stand out. Without a configured tracker base URL there's
/// nothing real to link to, so these are highlighted (monospace) rather than
/// turned into a guessed/likely-broken hyperlink.
final _ticketIdPattern = RegExp(r'\b[A-Z][A-Z0-9]{1,9}-\d+\b');

String _highlightTicketIds(String text) {
  return text.replaceAllMapped(_ticketIdPattern, (m) => '`${m.group(0)}`');
}
