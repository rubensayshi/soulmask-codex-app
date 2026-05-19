mod commands;

use std::sync::Mutex;
use std::sync::atomic::AtomicBool;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

/// Shared queue of screenshot paths waiting to be processed.
pub struct CaptureQueue(pub Mutex<Vec<String>>);

/// True while the processing loop is running.
pub struct ProcessingFlag(pub AtomicBool);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let shortcut_s = Shortcut::new(Some(Modifiers::ALT | Modifiers::SHIFT), Code::KeyS);
    let shortcut_p = Shortcut::new(Some(Modifiers::ALT | Modifiers::SHIFT), Code::KeyP);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(CaptureQueue(Mutex::new(vec![])))
        .manage(ProcessingFlag(std::sync::atomic::AtomicBool::new(false)))
        .invoke_handler(tauri::generate_handler![
            commands::process_images,
            commands::save_roster,
            commands::load_roster,
            commands::capture_screen,
            commands::debug_capture,
            commands::process_queue,
            commands::clear_queue,
        ])
        .setup(move |app| {
            let handle = app.handle().clone();

            // Alt+Shift+S — snapshot, enqueue, then auto-start processing if idle.
            // Each press spawns its own capture task; no deduplication needed since
            // captures are fast and the processing loop serialises work via ProcessingFlag.
            app.global_shortcut().on_shortcut(shortcut_s, move |_app, _shortcut, _event| {
                let hdl = handle.clone();
                tauri::async_runtime::spawn(async move {
                    commands::queue_capture_inner(&hdl).await;
                });
            })?;

            let handle2 = app.handle().clone();

            // Alt+Shift+P — manual fallback to kick off processing if auto-start stalled
            app.global_shortcut().on_shortcut(shortcut_p, move |_app, _shortcut, _event| {
                let hdl = handle2.clone();
                tauri::async_runtime::spawn(async move {
                    commands::try_start_processing(&hdl).await;
                });
            })?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
