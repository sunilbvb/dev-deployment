import 'dart:io';
import 'git_ops.dart';
import 'models.dart';

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
