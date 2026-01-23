use pyo3::prelude::*;
use std::cell::RefCell;
use std::sync::OnceLock;
use std::time::Duration;
use tokio::runtime::EnterGuard;
use tokio::runtime::Runtime;

// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

fn aptabase_runtime() -> &'static Runtime {
    static RT: OnceLock<Runtime> = OnceLock::new();
    RT.get_or_init(|| {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("failed to create tokio runtime for aptabase")
    })
}

fn ensure_tokio_runtime_entered() {
    thread_local! {
        static TOKIO_ENTER_GUARD: RefCell<Option<EnterGuard<'static>>> = RefCell::new(None);
    }

    TOKIO_ENTER_GUARD.with(|cell| {
        if cell.borrow().is_none() {
            *cell.borrow_mut() = Some(aptabase_runtime().enter());
        }
    });
}

pub fn tauri_generate_context() -> tauri::Context<tauri::Wry> {
    tauri::generate_context!()
}

#[pymodule(gil_used = false)]
#[pyo3(name = "ext_mod")]
pub mod ext_mod {
    use super::*;

    #[pymodule_init]
    fn init(module: &Bound<'_, PyModule>) -> PyResult<()> {
        ensure_tokio_runtime_entered();
        pytauri::pymodule_export(
            module,
            // i.e., `context_factory` function of python binding
            |_args, _kwargs| Ok(tauri_generate_context()),
            // i.e., `builder_factory` function of python binding
            |_args, _kwargs| {
                let builder = tauri::Builder::default()
                    .plugin(
                        tauri_plugin_aptabase::Builder::new("A-SH-3121700810")
                            .with_options(tauri_plugin_aptabase::InitOptions {
                                host: Some("https://analytics.kiv.cc".into()),
                                flush_interval: Some(Duration::from_secs(60)),
                                ..Default::default()
                            })
                            .build(),
                    )
                    .plugin(tauri_plugin_opener::init())
                    .plugin(tauri_plugin_process::init())
                    .plugin(tauri_plugin_updater::Builder::new().build())
                    .invoke_handler(tauri::generate_handler![greet])
                    .setup(|app| {
                        use tauri_plugin_aptabase::EventTracker;

                        ensure_tokio_runtime_entered();
                        let _ = app.track_event("app_started", None);

                        #[cfg(target_os = "macos")]
                        {
                            use tauri::Manager;

                            if let Some(webview) = app.get_webview("main") {
                                let _ = webview.with_webview(|webview| unsafe {
                                    let view: &objc2_web_kit::WKWebView = &*webview.inner().cast();
                                    if let Some(scroll_view) = view.enclosingScrollView() {
                                        scroll_view.setVerticalScrollElasticity(objc2_app_kit::NSScrollElasticity::None);
                                        scroll_view.setHorizontalScrollElasticity(objc2_app_kit::NSScrollElasticity::None);
                                    }
                                });
                            }
                        }

                        Ok(())
                    });
                Ok(builder)
            },
        )
    }
}
