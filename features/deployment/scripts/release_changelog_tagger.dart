// Backward-compatibility entrypoint delegating to release/release_changelog_tagger.dart
import 'release/release_changelog_tagger.dart' as tagger;

void main(List<String> args) => tagger.main(args);
