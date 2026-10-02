// Representation of release modes, commits, packages, and CLI options.

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
