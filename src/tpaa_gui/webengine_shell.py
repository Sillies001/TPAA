"""Fail-closed Qt WebEngine adapter for the v33 product shell."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from .local_backend import WebEngineBinding


class _ExactOriginInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, binding: WebEngineBinding, parent: QWebEngineProfile) -> None:
        super().__init__(parent)
        self._binding = binding

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:  # noqa: N802
        url = info.requestUrl()
        origin = f"{url.scheme()}://{url.host()}:{url.port()}"
        if origin != self._binding.origin:
            info.block(True)
            return
        info.setHttpHeader(b"Authorization", self._binding.authorization_header)
        info.setHttpHeader(b"X-TPAA-Desktop-Nonce", self._binding.desktop_nonce)


class _ExactOriginPage(QWebEnginePage):
    navigation_blocked = Signal(str)

    def __init__(self, profile: QWebEngineProfile, origin: str, parent: QWidget) -> None:
        super().__init__(profile, parent)
        self._origin = origin

    def acceptNavigationRequest(  # noqa: N802
        self,
        url: QUrl | str,
        navigation_type: QWebEnginePage.NavigationType,
        is_main_frame: bool,
    ) -> bool:
        del navigation_type
        target = QUrl(url) if isinstance(url, str) else url
        if is_main_frame:
            origin = f"{target.scheme()}://{target.host()}:{target.port()}"
            if origin != self._origin:
                self.navigation_blocked.emit(target.toString())
                return False
        return True


class WebEngineWorkspace(QStackedWidget):
    """Typed owner for WebEngine objects whose lifetime must match the workspace."""

    def __init__(self, parent: QWidget | None) -> None:
        super().__init__(parent)
        self._tpaa_web_profile: QWebEngineProfile | None = None
        self._tpaa_web_interceptor: _ExactOriginInterceptor | None = None
        self._tpaa_web_page: _ExactOriginPage | None = None
        self._tpaa_web_view: QWebEngineView | None = None


def create_webengine_workspace(
    parent: QWidget | None, binding: WebEngineBinding | None
) -> WebEngineWorkspace:
    """Create the v33 browser surface or an explicit backend-unavailable state."""

    stack = WebEngineWorkspace(parent)
    stack.setObjectName("tpaaV33WebEngineStack")
    unavailable = QWidget(stack)
    unavailable_layout = QVBoxLayout(unavailable)
    unavailable_label = QLabel(
        "产品界面暂不可用\n本地后端未就绪；系统已按设计保持失败关闭。",
        unavailable,
    )
    unavailable_label.setObjectName("tpaaV33BackendUnavailable")
    unavailable_layout.addWidget(unavailable_label)
    stack.addWidget(unavailable)
    if binding is None:
        stack.setCurrentWidget(unavailable)
        return stack

    profile = QWebEngineProfile(stack)
    if not profile.isOffTheRecord():
        raise RuntimeError("TPAA_WEBENGINE_PROFILE_MUST_BE_OFF_THE_RECORD")
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
    )
    interceptor = _ExactOriginInterceptor(binding, profile)
    profile.setUrlRequestInterceptor(interceptor)
    profile.downloadRequested.connect(lambda item: item.cancel())

    view = QWebEngineView(stack)
    view.setObjectName("tpaaV33WebEngineView")
    page = _ExactOriginPage(profile, binding.origin, view)
    settings = page.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
    view.setPage(page)
    stack.addWidget(view)
    stack.setCurrentWidget(view)

    def render_terminated(*_args: object) -> None:
        unavailable_label.setText(
            "产品界面渲染进程已停止\n请关闭并重新启动当前桌面会话。"
        )
        stack.setCurrentWidget(unavailable)

    page.renderProcessTerminated.connect(render_terminated)
    page.navigation_blocked.connect(
        lambda _url: unavailable_label.setText("已阻止离开本地受控产品源的导航。")
    )
    view.setUrl(QUrl(f"{binding.origin}/ui"))
    stack._tpaa_web_profile = profile
    stack._tpaa_web_interceptor = interceptor
    stack._tpaa_web_page = page
    stack._tpaa_web_view = view
    return stack


__all__ = ["WebEngineWorkspace", "create_webengine_workspace"]
