import 'dart:io';
import 'models.dart';

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
