/**
 * app_demo.js — Interactive Demo Mode Module
 * Provides simulated mock environment, sample apps, simulated terminal execution,
 * mock doctor diagnostics, mock APK downloads, and demo banners.
 */

function setupDemoCommands(appId) {
    state.commands = [
        {
            id: 'build_apk',
            key: 'flutter build apk --flavor dev -t lib/main_dev.dart',
            name: 'Build Android APK',
            category: 'android',
            flavor: 'dev',
            platform: 'android',
            command: 'flutter build apk --flavor dev -t lib/main_dev.dart',
            description: 'Compile debug APK with development backend credentials.',
            configured: true,
        },
        {
            id: 'build_apk_qa',
            key: 'flutter build apk --flavor qa -t lib/main_qa.dart',
            name: 'Build Android APK (QA)',
            category: 'android',
            flavor: 'qa',
            platform: 'android',
            command: 'flutter build apk --flavor qa -t lib/main_qa.dart',
            description: 'Compile testing APK for QA team distribution.',
            configured: true,
        },
        {
            id: 'build_aab_prod',
            key: 'flutter build appbundle --flavor prod -t lib/main.dart',
            name: 'Build App Bundle (AAB)',
            category: 'android',
            flavor: 'prod',
            platform: 'android',
            command: 'flutter build appbundle --flavor prod -t lib/main.dart',
            description: 'Compile release bundle with production signing.',
            templateId: 'build_aab',
            configured: true,
        },
        {
            id: 'deploy_play_store_prod',
            key: 'bundle exec fastlane android deploy_play_store flavor:prod',
            name: 'Upload to Google Play',
            category: 'android',
            flavor: 'prod',
            platform: 'android',
            command: 'bundle exec fastlane android deploy_play_store flavor:prod',
            description: 'Build and ship release AAB to Play Console track.',
            templateId: 'deploy_aab',
            configured: true,
        },
        {
            id: 'build_ipa_dev',
            key: 'flutter build ipa --flavor dev --export-method development',
            name: 'Build iOS IPA',
            category: 'ios',
            flavor: 'dev',
            platform: 'ios',
            command: 'flutter build ipa --flavor dev --export-method development',
            description: 'Build development iOS IPA for local device testing.',
            configured: true,
        },
        {
            id: 'deploy_testflight_prod',
            key: 'bundle exec fastlane ios deploy_testflight flavor:prod',
            name: 'Upload to TestFlight',
            category: 'ios',
            flavor: 'prod',
            platform: 'ios',
            command: 'bundle exec fastlane ios deploy_testflight flavor:prod',
            description: 'Build and ship release IPA to App Store Connect / TestFlight.',
            templateId: 'deploy_ipa',
            configured: true,
        },
    ];

    state.pipelines = [
        {
            id: 'pipe_release_prod',
            name: 'Full Store Release (Doctor → Build AAB → Upload)',
            app: appId,
            flavor: 'prod',
            steps: [
                { name: 'App Doctor Pre-flight', command: 'doctor run', continueOnFailure: false },
                { name: 'Build Production Bundle', command: 'flutter build appbundle --flavor prod', continueOnFailure: false },
                { name: 'Upload to Google Play', command: 'fastlane android upload_aab', continueOnFailure: false }
            ]
        }
    ];

    renderEnvTabs();
    renderCommands();
}

function runSimulatedDemoExecution(cmdText) {
    state.activeJobId = 'demo_job_42';
    els.runButton.disabled = true;
    els.stopJobBtn.disabled = false;
    startTimer();
    writeTerminal(`[DEMO] Starting: ${cmdText}`);

    setTimeout(() => writeTerminal('Resolving dependencies (flutter pub get)...'), 400);
    setTimeout(() => writeTerminal('✓ Dependencies up to date.'), 800);
    setTimeout(() => writeTerminal('Compiling release app bundle with target lib/main.dart...'), 1200);
    setTimeout(() => writeTerminal('✓ Built build/app/outputs/bundle/prodRelease/app-release.aab (24.2 MB)'), 1800);
    setTimeout(() => {
        writeTerminal('\n📦 Build Size Inspector: AAB: 24.2 MB (+3.8 MB, +18.0%) ⚠️');
        writeTerminal('⚠️  Size Warning: Build increased by +18.0% (+3.8 MB)!');
        writeTerminal('Completed successfully (demo mode)', 'success');
        showToast('Demo deployment command completed!');

        const mockBuildSize = {
            success: true,
            hasBaseline: true,
            artifactType: 'AAB',
            currentSizeBytes: 25375539,
            currentSizeFormatted: '24.2 MB',
            currentFilename: 'app-release.aab',
            currentArtifactPath: '/demo/flutter_monorepo/apps/customer_app/build/app/outputs/bundle/prodRelease/app-release.aab',
            previousBuild: { sizeFormatted: '20.4 MB', jobId: 'job_baseline' },
            deltaBytes: 3984588,
            deltaFormatted: '+3.8 MB',
            deltaPercent: 18.0,
            deltaPercentFormatted: '+18.0%',
            severity: 'warning',
            badgeVariant: 'warning',
            summary: 'AAB: 24.2 MB (+3.8 MB, +18.0%) ⚠️',
            warnings: ['Size Warning: Build increased by +18.0% (+3.8 MB)!'],
            inspection: {
                compressionRatio: 68.2,
                totalUncompressedFormatted: '76.1 MB',
                uncompressedAssets: [
                    { name: 'base/assets/videos/hero_walkthrough.mp4', sizeFormatted: '2.8 MB', warning: 'Raw uncompressed asset (STORED)' }
                ],
                largestFiles: [
                    { name: 'base/assets/videos/hero_walkthrough.mp4', compressedSizeFormatted: '2.8 MB', uncompressedSizeFormatted: '2.8 MB', compressType: 'stored' },
                    { name: 'base/lib/arm64-v8a/libapp.so', compressedSizeFormatted: '8.4 MB', uncompressedSizeFormatted: '22.1 MB', compressType: 'deflated' },
                    { name: 'base/dex/classes.dex', compressedSizeFormatted: '4.2 MB', uncompressedSizeFormatted: '11.8 MB', compressType: 'deflated' }
                ]
            },
            diff: {
                hasDiff: true,
                grownAssets: [
                    { name: 'base/lib/arm64-v8a/libapp.so', deltaBytes: 1048576, deltaFormatted: '+1.0 MB', currSizeFormatted: '8.4 MB', prevSizeFormatted: '7.4 MB' }
                ],
                addedAssets: [
                    { name: 'base/assets/videos/hero_walkthrough.mp4', sizeBytes: 2936012, sizeFormatted: '2.8 MB' }
                ],
                removedAssets: []
            }
        };
        if (typeof renderBuildSizeBanner === 'function') {
            renderBuildSizeBanner(mockBuildSize);
        }

        const mockApk = {
            success: true,
            hasApk: true,
            filename: 'app-qa-release.apk',
            sizeFormatted: '18.6 MB',
            path: '/demo/flutter_monorepo/apps/customer_app/build/app/outputs/apk/app-qa-release.apk',
            downloadUrl: 'http://192.168.1.50:18112/api/deployment/download/demo_job_42',
            qrText: 'http://192.168.1.50:18112/api/deployment/download/demo_job_42',
            lanIp: '192.168.1.50'
        };
        if (typeof renderApkBanner === 'function') {
            renderApkBanner(mockApk);
        }

        state.historyEntries.unshift({
            id: 'demo_job_42',
            app: state.selectedApp,
            flavor: state.selectedEnv,
            templateId: 'build_aab',
            status: 'success',
            completedAt: Date.now(),
            durationSeconds: 2,
            buildSize: mockBuildSize,
            artifact: { type: 'AAB', sizeFormatted: '24.2 MB' }
        });

        finishExecution();
    }, 2000);
}

function renderDemoDoctorDiagnostics() {
    setTimeout(() => {
        if (!els.doctorStatusBanner) return;
        const data = {
            success: true,
            overallStatus: 'warn',
            passCount: 10,
            warnCount: 2,
            failCount: 0,
            summary: 'Pre-flight check passed with 2 minor warnings. Ready to build.',
            durationSeconds: 0.6,
            checks: [
                { category: 'toolchain', name: 'Flutter SDK Toolchain', status: 'pass', details: 'Flutter 3.24.3 • channel stable' },
                { category: 'toolchain', name: 'Dart SDK', status: 'pass', details: 'Dart 3.5.3' },
                { category: 'toolchain', name: 'Fastlane Installation', status: 'pass', details: 'Fastlane 2.222.0 detected' },
                { category: 'project', name: 'Pubspec Dependencies', status: 'pass', details: 'All dependencies resolved cleanly' },
                { category: 'android', name: 'Android SDK & Build Tools', status: 'pass', details: 'API 34, compileSdkVersion 34' },
                { category: 'android', name: 'Android Keystore Validity', status: 'pass', details: 'upload.jks valid until 2051' },
                { category: 'ios', name: 'CocoaPods Dependencies', status: 'pass', details: 'Podfile and Podfile.lock in sync' },
                { category: 'ios', name: 'Apple Distribution Certificate', status: 'warn', details: 'Certificate expires in 18 days. Consider renewing soon.' },
                { category: 'credentials', name: 'App Store Connect API Key (.p8)', status: 'pass', details: 'AuthKey_ABCD1234.p8 configured' },
                { category: 'credentials', name: 'Google Play Service Account', status: 'pass', details: 'play-account.json verified' },
                { category: 'credentials', name: 'Firebase Project Match', status: 'pass', details: 'google-services.json matches flavor' },
                { category: 'git', name: 'Git Release Readiness', status: 'warn', details: 'Working tree has uncommitted files in assets/' },
            ]
        };

        els.doctorStatusBanner.dataset.status = 'warn';
        els.doctorOverallIcon.textContent = '⚠️';
        els.doctorOverallTitle.textContent = 'Environment Warnings Detected';
        els.doctorOverallSummary.textContent = data.summary;
        els.doctorScorePills.innerHTML = `
            <span class="ui-badge" data-variant="success">${data.passCount} Passed</span>
            <span class="ui-badge" data-variant="warning">${data.warnCount} Warnings</span>
        `;

        const categories = [
            { key: 'toolchain', title: 'SDK & Core Toolchain' },
            { key: 'project', title: 'Project Structure & Dependencies' },
            { key: 'android', title: 'Android Build Environment' },
            { key: 'ios', title: 'iOS Environment & Signing' },
            { key: 'credentials', title: 'Store Deployment Credentials' },
            { key: 'git', title: 'Git & Release Readiness' },
        ];

        let html = '';
        categories.forEach(cat => {
            const catChecks = data.checks.filter(c => c.category === cat.key);
            if (!catChecks.length) return;
            html += `
                <div class="doctor-category-card">
                    <div class="doctor-category-header">
                        <span>${escapeHtml(cat.title)}</span>
                        <span style="font-size: 0.72rem; opacity: 0.8;">${catChecks.length} checks</span>
                    </div>
                    <div>
            `;
            catChecks.forEach(c => {
                const badgeVariant = c.status === 'pass' ? 'success' : 'warning';
                const statusIcon = c.status === 'pass' ? 'check-circle' : 'alert-triangle';
                html += `
                    <div class="doctor-check-item">
                        <div class="doctor-check-icon ${c.status}"><i data-lucide="${statusIcon}"></i></div>
                        <div style="flex: 1;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
                                <span class="doctor-check-name">${escapeHtml(c.name)}</span>
                                <span class="ui-badge" data-variant="${badgeVariant}">${escapeHtml(c.status.toUpperCase())}</span>
                            </div>
                            <div class="doctor-check-details">${escapeHtml(c.details)}</div>
                        </div>
                    </div>
                `;
            });
            html += '</div></div>';
        });

        els.doctorChecklistContainer.innerHTML = html;
        if (els.doctorFooterDuration) els.doctorFooterDuration.textContent = 'Completed in 0.6s (demo mode)';
        if (els.recheckDoctorBtn) els.recheckDoctorBtn.disabled = false;
        refreshIcons();
    }, 600);
}

function startDemoMode() {
    state.isDemoMode = true;

    if (els.serverOfflineBanner) {
        els.serverOfflineBanner.style.display = 'none';
        els.serverOfflineBanner.classList.add('hidden');
    }
    if (els.demoModeBanner) {
        els.demoModeBanner.style.display = 'block';
        els.demoModeBanner.classList.remove('hidden');
    }

    // Sample Flutter Monorepo Apps
    state.apps = [
        {
            id: 'customer_app',
            name: 'Customer Store App',
            path: '/demo/flutter_monorepo/apps/customer_app',
            package_name: 'com.example.customer_app',
            bundle_id: 'com.example.customerApp',
            platforms: ['android', 'ios'],
            flavors: ['dev', 'qa', 'prod'],
            version: '2.4.1+42',
        },
        {
            id: 'driver_app',
            name: 'Driver Logistics App',
            path: '/demo/flutter_monorepo/apps/driver_app',
            package_name: 'com.example.driver_app',
            bundle_id: 'com.example.driverApp',
            platforms: ['android', 'ios'],
            flavors: ['dev', 'qa', 'prod'],
            version: '1.8.0+15',
        },
        {
            id: 'internal_pos',
            name: 'Store POS Terminal',
            path: '/demo/flutter_monorepo/apps/internal_pos',
            package_name: 'com.example.pos',
            platforms: ['android'],
            flavors: ['qa', 'prod'],
            version: '3.1.0+9',
        },
    ];

    if (typeof currentWorkspacesList !== 'undefined') {
        currentWorkspacesList = [
            { path: '/demo/flutter_monorepo', name: 'flutter_monorepo (Demo)', isDefault: true }
        ];
    }
    state.activeWorkspace = '/demo/flutter_monorepo';
    if (typeof renderActiveProject === 'function') renderActiveProject();
    if (typeof renderApps === 'function') renderApps();

    // Select first app
    if (typeof selectApp === 'function') selectApp('customer_app');

    // Mock Sentinel Data
    if (els.sentinelHeaderBadge && els.sentinelHeaderBadgeText) {
        els.sentinelHeaderBadge.style.display = 'inline-flex';
        els.sentinelHeaderBadge.classList.remove('hidden');
        els.sentinelHeaderBadgeText.textContent = '1 Expiry Alert';
        els.sentinelHeaderBadge.setAttribute('data-variant', 'warning');
    }

    showToast('Entered Interactive Demo Mode. Enjoy exploring features!');
    writeTerminal('🧪 Interactive Demo Mode initialized. Select an app, review commands, or run App Doctor.');
    refreshIcons();
}

function exitDemoMode() {
    state.isDemoMode = false;
    if (els.demoModeBanner) {
        els.demoModeBanner.style.display = 'none';
        els.demoModeBanner.classList.add('hidden');
    }
    if (typeof checkServerStatus === 'function') checkServerStatus();
    showToast('Exited Demo Mode');
}

// Wire Event Listeners
if (els.startDemoModeBtn) {
    els.startDemoModeBtn.addEventListener('click', startDemoMode);
}
if (els.exitDemoModeBtn) {
    els.exitDemoModeBtn.addEventListener('click', exitDemoMode);
}

// Window exports
window.setupDemoCommands = setupDemoCommands;
window.runSimulatedDemoExecution = runSimulatedDemoExecution;
window.renderDemoDoctorDiagnostics = renderDemoDoctorDiagnostics;
window.startDemoMode = startDemoMode;
window.exitDemoMode = exitDemoMode;
