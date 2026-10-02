import 'dart:io';

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
