import 'dart:io';
import 'models.dart';
import 'workspace_scanner.dart';

const _noiseCommitTypes = {'chore', 'docs', 'style', 'ci', 'test', 'build'};

final _ticketIdPattern = RegExp(r'\b[A-Z][A-Z0-9]{1,9}-\d+\b');

String _highlightTicketIds(String text) {
  return text.replaceAllMapped(_ticketIdPattern, (m) => '`${m.group(0)}`');
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

/// Prints every commit in the release window and why it was or was not included.
void printCommitTable({
  required List<GitCommit> commits,
  required PackageInfo target,
  required List<PackageInfo> internalDeps,
  required Map<String, List<GitCommit>> packageCommits,
  required List<GitCommit> workspaceCommits,
  required Iterable<PackageInfo> allPackages,
  required String? fromRef,
  required String toRef,
}) {
  print('');
  print('🔎 Commits in release window (${fromRef ?? 'first commit'} ➔ $toRef): ${commits.length}');
  if (commits.isEmpty) {
    print('   (none — nothing has changed since the last release)');
    print('');
    return;
  }
  final ownerOf = <String, String>{};
  for (final entry in packageCommits.entries) {
    for (final c in entry.value) {
      ownerOf.putIfAbsent(c.hash, () => entry.key == target.name ? 'app' : 'dependency ${entry.key}');
    }
  }
  for (final c in workspaceCommits) {
    ownerOf.putIfAbsent(c.hash, () => 'workspace / tooling');
  }
  var included = 0;
  for (final c in commits) {
    final owner = ownerOf[c.hash];
    final subject = c.subject.length > 72 ? '${c.subject.substring(0, 69)}...' : c.subject;
    if (owner != null) {
      included += 1;
      print('   ✔ ${c.shortHash}  $subject  [$owner]');
    } else {
      final others = {
        for (final f in c.changedFiles)
          for (final p in allPackages)
            if (p.name != target.name && isInPackage(f, p, allPackages)) p.name,
      };
      final reason = others.isNotEmpty ? 'belongs to ${others.join(', ')}' : 'no files in this app';
      print('   · ${c.shortHash}  $subject  (skipped: $reason)');
    }
  }
  print('   → $included included, ${commits.length - included} skipped');
  print('');
}
