import 'dart:io';
import 'models.dart';
import 'release_notifier.dart';

/// Git sub-commands that change the repository; these are echoed to the console
/// together with their outcome so every release step is auditable.
const _mutatingGitCommands = {'add', 'commit', 'tag', 'push'};

bool _isMutating(List<String> args) {
  if (args.isEmpty || !_mutatingGitCommands.contains(args.first)) return false;
  // `git tag -l` / `git tag --list` only read.
  return !(args.first == 'tag' && (args.contains('-l') || args.contains('--list')));
}

String _shellQuote(String arg) =>
    RegExp(r'^[A-Za-z0-9_./:@%+=,-]+$').hasMatch(arg) ? arg : "'${arg.replaceAll("'", "'\\''")}'";

Future<ProcessResult> runGit(
  List<String> args,
  String workingDirectory, {
  List<String>? displayArgs,
}) async {
  final echo = _isMutating(args);
  if (echo) {
    print('   \$ git ${(displayArgs ?? args).map(_shellQuote).join(' ')}   (in ${repoLabel(workingDirectory)})');
  }
  final res = await Process.run('git', args, workingDirectory: workingDirectory);
  if (echo) {
    final out = '${res.stdout}'.trim();
    final err = '${res.stderr}'.trim();
    if (res.exitCode == 0) {
      // push reports its result on stderr; show it so the remote outcome is visible.
      for (final line in [out, if (args.first == 'push') err].where((s) => s.isNotEmpty).expand((s) => s.split('\n'))) {
        print('     │ $line');
      }
      print('     └ ok');
    } else {
      for (final line in [out, err].where((s) => s.isNotEmpty).expand((s) => s.split('\n'))) {
        print('     │ $line');
      }
      print('     └ failed (exit ${res.exitCode})');
    }
  }
  return res;
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
    // --cleanup=verbatim keeps "### Features" headings (git strips '#' lines as comments
    // by default); -F must directly precede the file even when flags like -f were appended.
    final args = argsBeforeFile.where((a) => a != '-F').toList();
    final gitArgs = [args.first, '--cleanup=verbatim', ...args.skip(1), '-F'];
    final headline = message.split('\n').first.trim();
    return await runGit(
      [...gitArgs, messageFile.path],
      workingDirectory,
      displayArgs: [...gitArgs, '<message: "$headline" + ${message.split('\n').length - 1} more lines>'],
    );
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

/// Resolve the actual Git repository root that `path` lives inside. Returns
/// null if `path` doesn't exist or isn't inside a Git working tree.
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

const _primaryFlavorNames = {'prod', 'production', 'release', 'any', 'all', ''};

final _flavorSuffixedTagPattern = RegExp(r'-[A-Za-z]+$');

/// Returns the tag suffix (e.g. `-qa`) for a given flavor, or null when no
/// suffix should be applied (flavor unset, or one of the "primary" names above).
String? flavorTagSuffix(String? flavor) {
  if (flavor == null) return null;
  final normalized = flavor.trim().toLowerCase();
  if (_primaryFlavorNames.contains(normalized)) return null;
  return '-$normalized';
}

/// Find latest release tag matching <target_name>-v* or v*, scoped to the same
/// environment/flavor as the release currently being computed.
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

Future<bool> isUnpushedLocalReleaseAtHead(String tagName, String repoRoot) async {
  final tagCommit = await Process.run('git', ['rev-parse', '-q', '--verify', '$tagName^{commit}'], workingDirectory: repoRoot);
  if (tagCommit.exitCode != 0) return false;
  final head = await Process.run('git', ['rev-parse', 'HEAD'], workingDirectory: repoRoot);
  if (tagCommit.stdout.toString().trim() != head.stdout.toString().trim()) return false;
  final remoteTag = await Process.run('git', ['ls-remote', '--tags', 'origin', 'refs/tags/$tagName'], workingDirectory: repoRoot);
  return remoteTag.exitCode != 0 || remoteTag.stdout.toString().trim().isEmpty;
}

Future<void> pushExistingRelease({required String tagName, required String repoRoot}) async {
  final remoteRes = await runGit(['remote', 'get-url', 'origin'], repoRoot);
  if (remoteRes.exitCode != 0) {
    stderr.writeln('❌ No "origin" remote is configured in ${repoLabel(repoRoot)}. Add one with: git remote add origin <url>');
    exit(1);
  }
  print('🚀 Pushing existing release to origin → ${remoteRes.stdout.toString().trim()}');
  final problems = <String>[];
  if ((await runGit(['push', 'origin', 'HEAD'], repoRoot)).exitCode != 0) problems.add('commit push');
  if ((await runGit(['push', 'origin', tagName], repoRoot)).exitCode != 0) problems.add('tag push');
  await printReleaseSummary(tagName: tagName, repoRoot: repoRoot, pushed: problems.isEmpty);
  if (problems.isNotEmpty) {
    stderr.writeln('❌ Pushing failed (${problems.join(', ')}). Check the git output above.');
    exit(1);
  }
  print('\n🎉 [MODE 5 - FULL RELEASE] Existing release $tagName pushed to remote.');
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
