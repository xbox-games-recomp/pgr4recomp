// pgr4recomp - scripted synthetic gamepad for unattended test runs.
//
// Enabled by the PGR4_PAD environment variable; without it the default SDK input system is used unchanged.
// Synthetic devices are routed to guest user 0 and merged with any real pad, so a user can still play along.
//
// PGR4_PAD is a comma-separated list, times in seconds from driver setup:
//   12:A          tap A at t=12 s (held 150 ms)
//   15:START:400  tap START at t=15 s, held 400 ms
//   ~3:A          tap A every 3 s, forever
//   ~3@20:A       tap A every 3 s starting at t=20 s
// Buttons: A B X Y START BACK UP DOWN LEFT RIGHT LB RB LS RS LT RT (LT/RT = full trigger).
// Analog: NAME=value for LT RT (0..1) and LX LY RX RY (-1..1), e.g. `0:RT=0.6:5000` (60% throttle for 5 s),
// `0:LX=-0.4:300` (steer left 40% for 300 ms). Overlapping analog entries: the latest-starting one wins.
//
// PGR4_PAD_FILE names a command file for live control: whenever its mtime changes, its contents (same syntax)
// are queued with times relative to that moment, e.g. `Set-Content $f '0:START,1:DOWN,2:A'`.

#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>
#include <vector>

#include <rex/input/input_driver.h>
#include <rex/input/input_system.h>
#include <rex/logging.h>

namespace pgr4 {

using rex::X_RESULT;
using rex::X_STATUS;

class ScriptedInputDriver final : public rex::input::InputDriver {
 public:
  struct Press {
    double at = 0;      // first press, seconds
    double every = 0;   // repeat period, 0 = once
    double hold = 0.15;
    uint16_t buttons = 0;
    int axis = -1;      // kLT, kRT, kLX, kLY, kRX, kRY or -1
    float value = 0;
  };
  enum Axis { kLT, kRT, kLX, kLY, kRX, kRY, kAxisCount };

  ScriptedInputDriver(std::vector<Press> script, std::string command_file)
      : InputDriver(nullptr, 0), script_(std::move(script)), command_file_(std::move(command_file)) {}

  static std::vector<Press> Parse(std::string_view spec) {
    std::vector<Press> out;
    while (!spec.empty()) {
      auto comma = spec.find(',');
      std::string item(spec.substr(0, comma));
      spec = comma == std::string_view::npos ? std::string_view{} : spec.substr(comma + 1);
      std::vector<std::string> f;
      for (size_t p = 0, q; p <= item.size(); p = q + 1) {
        q = item.find(':', p);
        if (q == std::string::npos) q = item.size();
        f.push_back(item.substr(p, q - p));
      }
      if (f.size() < 2) continue;
      Press press;
      std::string& t = f[0];
      if (!t.empty() && t[0] == '~') {
        auto at_pos = t.find('@');
        press.every = std::atof(t.substr(1, at_pos - 1).c_str());
        press.at = at_pos == std::string::npos ? press.every : std::atof(t.substr(at_pos + 1).c_str());
      } else {
        press.at = std::atof(t.c_str());
      }
      if (!ButtonFromName(f[1], press)) {
        REXLOG_WARN("PGR4_PAD: unknown button '{}'", f[1]);
        continue;
      }
      if (f.size() > 2) press.hold = std::atof(f[2].c_str()) / 1000.0;
      out.push_back(press);
    }
    return out;
  }

  X_STATUS Setup() override {
    start_ = std::chrono::steady_clock::now();
    REXLOG_INFO("PGR4_PAD: scripted pad active with {} entries", script_.size());
    return X_STATUS_SUCCESS;
  }

  void EnumerateDevices(std::vector<rex::input::DeviceInfo>& out) override {
    rex::input::DeviceInfo info;
    info.id = kDevice;
    info.name = "PGR4 scripted pad";
    info.synthetic = true;
    out.push_back(info);
  }

  X_RESULT GetDeviceState(rex::input::DeviceId id, rex::input::X_INPUT_STATE* out_state) override {
    if (id != kDevice) return X_ERROR_DEVICE_NOT_CONNECTED;
    std::lock_guard lock(mutex_);
    double now = std::chrono::duration<double>(std::chrono::steady_clock::now() - start_).count();
    PollCommandFile(now);
    std::erase_if(script_, [now](const Press& p) { return p.every == 0 && now >= p.at + p.hold; });
    uint16_t buttons = 0;
    float axes[kAxisCount] = {};
    double axis_start[kAxisCount];
    std::fill(std::begin(axis_start), std::end(axis_start), -1.0);
    for (const auto& p : script_) {
      if (now < p.at) continue;
      double phase = p.every > 0 ? std::fmod(now - p.at, p.every) : now - p.at;
      if (phase >= p.hold) continue;
      buttons |= p.buttons;
      if (p.axis >= 0 && p.at >= axis_start[p.axis]) {
        axes[p.axis] = p.value;
        axis_start[p.axis] = p.at;
      }
    }
    // Packet number changes with any state change; the log only records button changes (analog would spam).
    uint32_t key = buttons;
    for (float a : axes) key = key * 31 + static_cast<uint32_t>(static_cast<int32_t>(a * 1000));
    if (key != last_key_) {
      ++packet_;
      last_key_ = key;
    }
    if (buttons != last_buttons_) {
      if (buttons) REXLOG_INFO("PGR4_PAD: t={:.2f}s press 0x{:04X}", now, buttons);
      last_buttons_ = buttons;
    }
    auto trigger = [](float v) { return static_cast<uint8_t>(std::clamp(v, 0.0f, 1.0f) * 255.0f); };
    auto stick = [](float v) { return static_cast<int16_t>(std::clamp(v, -1.0f, 1.0f) * 32767.0f); };
    if (out_state) {
      std::memset(out_state, 0, sizeof(*out_state));
      out_state->packet_number = packet_;
      out_state->gamepad.buttons = buttons;
      out_state->gamepad.left_trigger = trigger(axes[kLT]);
      out_state->gamepad.right_trigger = trigger(axes[kRT]);
      out_state->gamepad.thumb_lx = stick(axes[kLX]);
      out_state->gamepad.thumb_ly = stick(axes[kLY]);
      out_state->gamepad.thumb_rx = stick(axes[kRX]);
      out_state->gamepad.thumb_ry = stick(axes[kRY]);
    }
    return X_ERROR_SUCCESS;
  }

  X_RESULT GetDeviceCapabilities(rex::input::DeviceId id, uint32_t,
                                 rex::input::X_INPUT_CAPABILITIES* out_caps) override {
    if (id != kDevice) return X_ERROR_DEVICE_NOT_CONNECTED;
    if (out_caps) {
      std::memset(out_caps, 0, sizeof(*out_caps));
      out_caps->type = 0x01;      // XINPUT_DEVTYPE_GAMEPAD
      out_caps->sub_type = 0x01;  // XINPUT_DEVSUBTYPE_GAMEPAD
      out_caps->gamepad.buttons = 0xFFFF;
      out_caps->gamepad.left_trigger = 0xFF;
      out_caps->gamepad.right_trigger = 0xFF;
    }
    return X_ERROR_SUCCESS;
  }

  X_RESULT SetDeviceVibration(rex::input::DeviceId id, rex::input::X_INPUT_VIBRATION*) override {
    return id == kDevice ? X_ERROR_SUCCESS : X_ERROR_DEVICE_NOT_CONNECTED;
  }

  X_RESULT GetDeviceKeystroke(rex::input::DeviceId id, uint32_t,
                              rex::input::X_INPUT_KEYSTROKE*) override {
    return id == kDevice ? X_ERROR_EMPTY : X_ERROR_DEVICE_NOT_CONNECTED;
  }

  // Default SDK input system plus the scripted pad when PGR4_PAD is set.
  static std::unique_ptr<rex::system::IInputSystem> CreateInputSystem(bool tool_mode) {
    auto input = rex::input::CreateDefaultInputSystem(tool_mode);
    const char* spec = std::getenv("PGR4_PAD");
    const char* file = std::getenv("PGR4_PAD_FILE");
    if (!tool_mode && ((spec && *spec) || (file && *file))) {
      auto driver = std::make_unique<ScriptedInputDriver>(Parse(spec ? spec : ""), file ? file : "");
      if (driver->Setup() == X_STATUS_SUCCESS) input->AddDriver(std::move(driver));
    }
    return input;
  }

 private:
  // Checks the live command file at most every 100 ms; a new mtime queues its contents relative to `now`.
  void PollCommandFile(double now) {
    if (command_file_.empty() || now - last_poll_ < 0.1) return;
    last_poll_ = now;
    std::error_code ec;
    auto mtime = std::filesystem::last_write_time(command_file_, ec);
    if (ec || mtime == command_mtime_) return;
    command_mtime_ = mtime;
    std::ifstream in(command_file_);
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    for (char& c : text) {
      if (c == '\r' || c == '\n') c = ',';
    }
    auto presses = Parse(text);
    for (auto& p : presses) p.at += now;
    REXLOG_INFO("PGR4_PAD: t={:.2f}s queued {} command(s) from file: {}", now, presses.size(), text);
    script_.insert(script_.end(), presses.begin(), presses.end());
  }

  static constexpr rex::input::DeviceId kDevice = static_cast<rex::input::DeviceId>(0x50475234);  // "PGR4"

  static bool ButtonFromName(const std::string& n, Press& p) {
    static const struct { const char* name; uint16_t bit; } kButtons[] = {
        {"UP", 0x0001},    {"DOWN", 0x0002}, {"LEFT", 0x0004}, {"RIGHT", 0x0008},
        {"START", 0x0010}, {"BACK", 0x0020}, {"LS", 0x0040},   {"RS", 0x0080},
        {"LB", 0x0100},    {"RB", 0x0200},   {"A", 0x1000},    {"B", 0x2000},
        {"X", 0x4000},     {"Y", 0x8000}};
    static const char* const kAxes[kAxisCount] = {"LT", "RT", "LX", "LY", "RX", "RY"};
    auto eq = n.find('=');
    std::string name = n.substr(0, eq);
    for (int a = 0; a < kAxisCount; ++a) {
      if (name == kAxes[a]) {
        p.axis = a;
        p.value = eq == std::string::npos ? 1.0f : static_cast<float>(std::atof(n.c_str() + eq + 1));
        return true;
      }
    }
    for (const auto& b : kButtons) {
      if (n == b.name) {
        p.buttons = b.bit;
        return true;
      }
    }
    return false;
  }

  std::vector<Press> script_;
  std::string command_file_;
  std::filesystem::file_time_type command_mtime_{};
  double last_poll_ = -1;
  std::mutex mutex_;
  std::chrono::steady_clock::time_point start_;
  uint32_t packet_ = 0;
  uint32_t last_key_ = 0;
  uint16_t last_buttons_ = 0;
};

}  // namespace pgr4
