mod commands;

use std::sync::Mutex;
use std::sync::atomic::AtomicBool;
use tauri_plugin_global_shortcut::{Code, Modifiers, Shortcut, ShortcutState};

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
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_shortcuts(["alt+shift+s", "alt+shift+p"]).unwrap()
                .with_handler(move |app, shortcut, event| {
                    if event.state != ShortcutState::Pressed { return; }
                    if shortcut == &shortcut_s {
                        let hdl = app.clone();
                        tauri::async_runtime::spawn(async move {
                            commands::queue_capture_inner(&hdl).await;
                        });
                    } else if shortcut == &shortcut_p {
                        let hdl = app.clone();
                        tauri::async_runtime::spawn(async move {
                            commands::try_start_processing(&hdl).await;
                        });
                    }
                })
                .build(),
        )
        .manage(CaptureQueue(Mutex::new(vec![])))
        .manage(ProcessingFlag(std::sync::atomic::AtomicBool::new(false)))
        .invoke_handler(tauri::generate_handler![
            commands::process_images,
            commands::import_images,
            commands::save_roster,
            commands::load_roster,
            commands::capture_screen,
            commands::debug_capture,
            commands::process_queue,
            commands::clear_queue,
        ])
        .setup(move |_app| {
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
