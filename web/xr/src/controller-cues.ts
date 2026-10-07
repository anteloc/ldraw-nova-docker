// Button tags on IWSDK's controller models, facing the user: Menu on Y/B
// while the menu is hidden, and Recenter on X/A throughout the session.
import {
  Box3,
  CanvasTexture,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  type Object3D,
  PlaneGeometry,
  Quaternion,
  SRGBColorSpace,
  Vector3,
  type World,
} from "@iwsdk/core";

type Hand = "left" | "right";
/** Out of the button, in the controller model's space, if its press animation doesn't say (Touch Plus). */
const OUT_OF_BUTTON = new Vector3(0, 0.8, -0.6).normalize();
interface Cue {
  label: "Menu" | "Recenter";
  /** Nodes in the WebXR input profile models (Quest Touch, Touch Plus, Touch Pro). */
  buttons: Record<Hand, string>;
  width: number;
  lift: number;
}

/** The parts of IWSDK's AnimatedController this reads (not public API). */
interface ControllerVisual {
  model: Object3D & { refMesh?: Object3D };
  animatedComponents?: { node: Object3D; transformRange: { min: { position: Vector3 }; max: { position: Vector3 } } }[];
}

const _matrix = new Matrix4();
const _box = new Box3();
const _quaternion = new Quaternion();
const _head = new Quaternion();

export class ControllerCues {
  private readonly menu: ButtonCues;
  private readonly recenter: ButtonCues;

  constructor(world: World) {
    this.menu = new ButtonCues(world, {
      label: "Menu", buttons: { left: "y_button", right: "b_button" }, width: 0.045, lift: 0.026,
    });
    // Stagger the heights so both labels remain readable above adjacent buttons.
    this.recenter = new ButtonCues(world, {
      label: "Recenter", buttons: { left: "x_button", right: "a_button" }, width: 0.065, lift: 0.071,
    });
  }

  update(menuHidden: boolean) {
    this.menu.update(menuHidden);
    this.recenter.update(true);
  }
}

class ButtonCues {
  private readonly tags: Record<Hand, Mesh>;
  /** The controller model each tag is on (a new one, if the visual is swapped). */
  private readonly on: Record<Hand, Object3D | null> = { left: null, right: null };

  constructor(private readonly world: World, private readonly cue: Cue) {
    const texture = drawTag(cue.label);
    const geometry = new PlaneGeometry(cue.width, (cue.width * texture.image.height) / texture.image.width);
    // On top, untouched by tone mapping, and never a pointer target.
    const material = new MeshBasicMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false, toneMapped: false });
    const tag = () => {
      const mesh = new Mesh(geometry, material);
      mesh.name = `${cue.label.toLowerCase()}-cue`;
      mesh.renderOrder = 1001;
      mesh.visible = false;
      (mesh as unknown as { pointerEvents: string }).pointerEvents = "none";
      return mesh;
    };
    this.tags = { left: tag(), right: tag() };
  }

  /** Every frame: show on connected controllers, facing the user. */
  update(show: boolean) {
    this.world.player.head.getWorldQuaternion(_head);
    for (const hand of ["left", "right"] as const) {
      const tag = this.tags[hand];
      const adapter = this.world.input.xr.visualAdapters.controller[hand];
      const visual = adapter.visual as unknown as ControllerVisual | undefined;
      if (visual && this.on[hand] !== visual.model) this.attach(hand, visual);
      tag.visible = show && adapter.connected && this.on[hand] === visual?.model && !!tag.parent;
      if (tag.visible) tag.quaternion.copy(tag.parent!.getWorldQuaternion(_quaternion).invert().multiply(_head)); // faces you
    }
  }

  /** Puts the tag just off the button, along the way the button pops out. */
  private attach(hand: Hand, visual: ControllerVisual) {
    this.on[hand] = visual.model;
    const tag = this.tags[hand];
    tag.removeFromParent();
    // FlexBatchedMesh draws the model's meshes from `refMesh`: the nodes are there.
    const root = visual.model.refMesh ?? visual.model;
    const button = root.getObjectByName(this.cue.buttons[hand]);
    if (!button) return;
    const centre = new Box3();
    button.traverse((object) => {
      const mesh = object as Mesh;
      if (!mesh.isMesh) return;
      mesh.geometry.computeBoundingBox();
      centre.union(_box.copy(mesh.geometry.boundingBox!).applyMatrix4(modelMatrix(mesh, root)));
    });
    if (centre.isEmpty()) return;
    // Its press animation moves it from up (min) to down (max): out is the other way.
    const press = visual.animatedComponents?.find((c) => c.node === button || c.node.getObjectById(button.id));
    const out = press
      ? press.transformRange.min.position.clone().sub(press.transformRange.max.position).transformDirection(modelMatrix(press.node.parent!, root))
      : OUT_OF_BUTTON.clone();
    if (!(out.lengthSq() > 0)) out.copy(OUT_OF_BUTTON);
    tag.position.copy(centre.getCenter(new Vector3())).addScaledVector(out, this.cue.lift);
    visual.model.add(tag);
  }
}

/** `object`'s transform in the model's space (as FlexBatchedMesh composes it: without the root's own). */
function modelMatrix(object: Object3D, root: Object3D) {
  _matrix.identity();
  for (let o: Object3D | null = object; o && o !== root; o = o.parent) {
    o.updateMatrix();
    _matrix.premultiply(o.matrix);
  }
  return _matrix;
}

/** A dark pill with an icon, label, and point towards the button. */
function drawTag(label: Cue["label"]) {
  const canvas = document.createElement("canvas");
  canvas.width = label === "Menu" ? 512 : 736;
  canvas.height = 208;
  const g = canvas.getContext("2d")!;
  g.beginPath();
  g.roundRect(12, 12, canvas.width - 24, 148, 74);
  const centre = canvas.width / 2;
  g.moveTo(centre - 30, 158);
  g.lineTo(centre, 196);
  g.lineTo(centre + 30, 158);
  g.closePath();
  g.fillStyle = "rgba(24, 24, 27, 0.9)";
  g.fill();
  g.lineWidth = 8;
  g.strokeStyle = "rgba(255, 255, 255, 0.95)";
  g.stroke();
  g.fillStyle = "#ffffff";
  if (label === "Menu") {
    for (const y of [56, 80, 104]) {
      g.beginPath();
      g.roundRect(78, y, 72, 13, 6.5);
      g.fill();
    }
  } else {
    // Crosshair: bring the model back to the centre of the view.
    g.beginPath();
    g.arc(112, 86, 28, 0, Math.PI * 2);
    g.moveTo(112, 42); g.lineTo(112, 68);
    g.moveTo(112, 104); g.lineTo(112, 130);
    g.moveTo(68, 86); g.lineTo(94, 86);
    g.moveTo(130, 86); g.lineTo(156, 86);
    g.stroke();
  }
  g.font = "700 92px system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
  g.textBaseline = "middle";
  g.fillText(label, 180, 90);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}
