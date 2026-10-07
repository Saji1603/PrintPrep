figma.showUI(__html__, {
  width: 460,
  height: 720,
});

function sendSelection() {
  const selection = figma.currentPage.selection;

  if (selection.length === 0) {
    figma.ui.postMessage({
      type: "selection",
      data: null,
    });
    return;
  }

  const node = selection[0];

  figma.ui.postMessage({
    type: "selection",
    data: {
      id: node.id,
      name: node.name,
      type: node.type,
      width: Math.round(node.width),
      height: Math.round(node.height),
    },
  });
}

sendSelection();

figma.on("selectionchange", () => {
  sendSelection();
});

figma.ui.onmessage = async (msg) => {
  try {
    if (msg.type === "export-selection") {
      const selection = figma.currentPage.selection;

      if (selection.length === 0) {
        figma.ui.postMessage({
          type: "export-error",
          message: "Please select a frame or artwork first.",
        });
        return;
      }

      const node = selection[0];

      if (!("exportAsync" in node)) {
        figma.ui.postMessage({
          type: "export-error",
          message: "This layer cannot be exported.",
        });
        return;
      }

      const bytes = await node.exportAsync({
        format: "PNG",
        constraint: {
          type: "SCALE",
          value: 2,
        },
      });

      const binary = Array.from(bytes);

      figma.ui.postMessage({
        type: "exported-image",
        name: node.name,
        width: Math.round(node.width),
        height: Math.round(node.height),
        bytes: binary,
      });
    }

    if (msg.type === "close") {
      figma.closePlugin();
    }
  } catch (error) {
    figma.ui.postMessage({
      type: "export-error",
      message:
        error instanceof Error
          ? error.message
          : "Unable to export the selected artwork.",
    });
  }
};