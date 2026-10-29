// pgr4recomp - ReXGlue Recompiled Project
//
// Customize your app by overriding virtual hooks from rex::ReXApp.

#pragma once

#include <rex/cvar.h>
#include <rex/rex_app.h>
#include <rex/system/gpu_plugin.h>

#include "scripted_input.h"

class Pgr4recompApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(
      rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<Pgr4recompApp>(new Pgr4recompApp(ctx, "pgr4recomp",
        PPCImageConfig));
  }

  // The SDK's gpu_plugin cvar defaults to "" (no GPU emulation); PGR4 needs the Xenos backend.
  // The plugin is loaded here rather than by the SDK right after this hook so that its cvars are
  // registered and can be given PGR4 defaults (command line / config values still win).
  void OnPreSetup(rex::RuntimeConfig& config) override {
    if (config.gpu_plugin.empty()) config.gpu_plugin = "xenos";
    config.graphics = rex::system::LoadGpuPlugin(config.gpu_plugin);  // null -> SDK retries, reports
    // The host render target path (RTV, the D3D12 default) turns the front end after the title
    // black; the EDRAM-accurate ROV path renders it (NOTES 10).
    if (rex::cvar::GetFlagSource("render_target_path_d3d12") == rex::cvar::Source::kDefault) {
      rex::cvar::SetFlagByName("render_target_path_d3d12", "rov");
    }
    config.input_factory = pgr4::ScriptedInputDriver::CreateInputSystem;  // == SDK default unless PGR4_PAD set
  }

  // Override virtual hooks for customization:
  // void OnPostInitLogging() override {}
  // void OnLoadXexImage(std::string& xex_image) override {}
  // void OnPostLoadXexImage() override {}
  // void OnPostSetup() override {}
  // void OnCreateDialogs(rex::ui::ImGuiDrawer* drawer) override {}
  // std::unique_ptr<rex::ui::ImGuiDialog> CreateAchievementsOverlay() override;
  // std::unique_ptr<rex::ui::AchievementNotificationDialog>
  // CreateAchievementNotificationDialog() override;
  // void OnShutdown() override {}
  // void OnConfigurePaths(rex::PathConfig& paths) override {}
};
