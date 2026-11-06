import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    width: 1600
    height: 900
    color: themeName === "light" ? "#eef2f5" : (themeName === "tactical" ? "#071510" : "#0b1017")

    property string viewId: g0ViewId
    property string themeName: g0ThemeName
    property var fixture: JSON.parse(g0FixtureJson)
    property var current: fixture[viewId]
    property color surface: themeName === "light" ? "#ffffff" : (themeName === "tactical" ? "#0d2119" : "#141b24")
    property color surface2: themeName === "light" ? "#e3e9ee" : (themeName === "tactical" ? "#102c20" : "#1a2430")
    property color border: themeName === "light" ? "#b6c2cc" : (themeName === "tactical" ? "#285d44" : "#344454")
    property color textMain: themeName === "light" ? "#16202a" : "#e5edf5"
    property color textMuted: themeName === "light" ? "#586977" : "#8fa3b5"
    property color accent: themeName === "tactical" ? "#36d17d" : (themeName === "light" ? "#1769aa" : "#4aa8ff")
    property string contractNote: viewId === "V03" ? "仅精确历史回放\n禁止最新值回退" :
                                  (viewId === "V04" ? "目标 Pᵢ 不得由 Ground Truth 填补\n缺失证据必须显式不可用" :
                                  (viewId === "V08" ? "成员 Pᵢ/Aᵢ 分别保留\n无通信证据不画共享关系" :
                                  (viewId === "V24" ? "仅由 V08 条件进入\n不形成综合总分" :
                                  (viewId === "V26" ? "每枚发射一个 WE\n齐射只通过 Cluster 关联" :
                                  "所有数值来自受控 API\n不在前端推导业务结论"))))

    component LabelText: Text {
        color: root.textMain
        font.family: "Microsoft YaHei UI"
        renderType: Text.QtRendering
    }

    Rectangle {
        id: titleBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 44
        color: root.surface2
        border.color: root.border

        LabelText {
            anchors.left: parent.left
            anchors.leftMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            text: "TPAA 训练复盘与评估系统"
            font.pixelSize: 17
            font.bold: true
        }
        LabelText {
            anchors.right: parent.right
            anchors.rightMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            text: "G0 QML 技术样板 · 合同数据"
            color: root.textMuted
            font.pixelSize: 12
        }
    }

    Rectangle {
        id: ribbon
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: titleBar.bottom
        height: 108
        color: root.surface
        border.color: root.border

        Row {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10
            Repeater {
                model: ["总览", "训练评估", "回放", "装备性能", "数据可信度", "报告", "管理"]
                delegate: Rectangle {
                    required property string modelData
                    width: modelData === "训练评估" ? 132 : 112
                    height: 78
                    radius: 4
                    color: (root.viewId === "V01" && modelData === "总览") ||
                           (root.viewId === "V03" && modelData === "回放") ||
                           (root.viewId === "V24" && modelData === "训练评估") ? root.surface2 : "transparent"
                    border.color: color === "transparent" ? "transparent" : root.accent
                    LabelText {
                        anchors.centerIn: parent
                        text: parent.modelData
                        color: parent.border.color === root.accent ? root.accent : root.textMain
                        font.pixelSize: 14
                    }
                }
            }
        }
    }

    Rectangle {
        id: contextBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: ribbon.bottom
        height: 42
        color: root.surface2
        border.color: root.border
        Row {
            anchors.fill: parent
            anchors.margins: 9
            spacing: 18
            LabelText { text: "科目：" + root.fixture.context.course; color: root.accent; font.pixelSize: 13 }
            LabelText { text: "架次：" + root.fixture.context.episode_id; font.pixelSize: 13 }
            LabelText { text: "发布：" + root.fixture.context.release_id; font.pixelSize: 13 }
            LabelText { text: "状态：" + root.fixture.context.readiness; font.pixelSize: 13 }
        }
    }

    Rectangle {
        id: navigation
        anchors.left: parent.left
        anchors.top: contextBar.bottom
        anchors.bottom: statusBar.top
        width: 230
        color: root.surface2
        border.color: root.border
        Column {
            anchors.fill: parent
            anchors.margins: 13
            spacing: 8
            LabelText { text: "当前任务"; color: root.textMuted; font.pixelSize: 12 }
            Rectangle {
                width: parent.width
                height: 52
                radius: 4
                color: root.surface
                border.color: root.accent
                LabelText {
                    anchors.fill: parent
                    anchors.margins: 10
                    verticalAlignment: Text.AlignVCenter
                    text: root.viewId + " · " + root.current.title
                    color: root.accent
                    font.pixelSize: 14
                    font.bold: true
                }
            }
            LabelText { text: "合同约束"; color: root.textMuted; font.pixelSize: 12; topPadding: 14 }
            LabelText {
                width: parent.width
                wrapMode: Text.WordWrap
                text: root.contractNote
                font.pixelSize: 13
                lineHeight: 1.45
            }
        }
    }

    Item {
        anchors.left: navigation.right
        anchors.right: parent.right
        anchors.top: contextBar.bottom
        anchors.bottom: statusBar.top

        LabelText {
            id: pageTitle
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 18
            height: 42
            text: root.current.title
            font.pixelSize: 24
            font.bold: true
        }

        Grid {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: pageTitle.bottom
            anchors.bottom: parent.bottom
            anchors.margins: 18
            columns: 3
            spacing: 12
            Repeater {
                model: root.current.sections
                delegate: Rectangle {
                    required property string modelData
                    width: (parent.width - 24) / 3
                    height: (parent.height - 12) / 2
                    radius: 5
                    color: root.surface
                    border.color: root.border
                    LabelText {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.margins: 13
                        text: parent.modelData
                        color: root.accent
                        font.pixelSize: 15
                        font.bold: true
                    }
                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        anchors.topMargin: 52
                        anchors.bottomMargin: 15
                        radius: 3
                        color: root.surface2
                        border.color: root.border
                        Canvas {
                            anchors.fill: parent
                            anchors.margins: 10
                            onPaint: {
                                const ctx = getContext("2d")
                                ctx.reset()
                                ctx.strokeStyle = root.accent
                                ctx.lineWidth = 2
                                ctx.beginPath()
                                ctx.moveTo(0, height * 0.72)
                                ctx.lineTo(width * 0.18, height * 0.48)
                                ctx.lineTo(width * 0.35, height * 0.62)
                                ctx.lineTo(width * 0.55, height * 0.30)
                                ctx.lineTo(width * 0.74, height * 0.42)
                                ctx.lineTo(width, height * 0.18)
                                ctx.stroke()
                            }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        id: statusBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 30
        color: root.surface2
        border.color: root.border
        LabelText {
            anchors.left: parent.left
            anchors.leftMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            text: "合同夹具：TPAA_GUI_G0_SPIKE_FIXTURE_V1　|　后端状态：" + root.fixture.context.readiness
            color: root.textMuted
            font.pixelSize: 11
        }
    }
}
