// Moving the model around in mixed reality, with IWSDK's built-ins:
//
// * Point at it and hold the trigger (or pinch) to move and turn it from where
//   you are (DistanceGrabbable: IWSDK's near grabs don't take rays, far ones do).
// * Point at it and push that hand's thumbstick: up or down scales it, left or
//   right turns it (StickControl).
// * Point at a real table or floor with either hand and press the trigger (or
//   pinch) to put it there: a laser and a ring show where (SurfacePointer).
// * Presets: real LEGO size, tabletop, and walk-in (minifig scale, on the floor).
// * Locomotion (thumbsticks, when not pointing at the model) over an invisible
//   floor, handy at walk-in scale.
import {
  BoxGeometry,
  createSystem,
  CylinderGeometry,
  DistanceGrabbable,
  type Entity,
  EnvironmentRaycastTarget,
  Euler,
  Grabbed,
  Group,
  Hovered,
  type InputActionBinding,
  InputComponent,
  LocomotionEnvironment,
  Mesh,
  MeshBasicMaterial,
  PlaneGeometry,
  Quaternion,
  RaycastSpace,
  RayInteractable,
  RingGeometry,
  MovementMode,
  Vector3,
  type World,
} from "@iwsdk/core";
import { RayDisplayMode } from "@iwsdk/xr-input";
import type { BatchedModel } from "./batching";

/** Tabletop preset: the model's longest side, metres. */
const TABLETOP_SIZE = 0.6;
/** Walk-in preset: minifig (about 4 cm) to person (about 1.8 m). */
export const WALK_IN_SCALE = 45;
const SCALE_MIN = 0.02;
const SCALE_MAX = 60;

/** Marks a geometry as having a BVH already (see PlacedModel). */
const NO_BOUNDS_TREE = Object.freeze({ placeholder: true });

const _up = new Vector3(0, 1, 0);
const _head = new Vector3();
const _forward = new Vector3();
const _euler = new Euler(0, 0, 0, "YXZ");
const _turn = new Quaternion();

/** The model in the world: a holder whose origin is the centre of the model's base. */
export class PlacedModel {
  readonly holder = new Group();
  readonly entity: Entity;
  private readonly size: Vector3;
  /** What pointers and hands hit: a plain box, not the model's thousands of parts. */
  private readonly proxy: Mesh;

  constructor(world: World, model: BatchedModel) {
    const { bounds } = model;
    this.size = bounds.getSize(new Vector3());
    // Base centre at the holder's origin: placing puts the base on the surface,
    // and scaling grows the model up from it.
    model.root.position.set(-(bounds.min.x + bounds.max.x) / 2, -bounds.min.y, -(bounds.min.z + bounds.max.z) / 2);
    this.holder.name = "model";
    this.holder.add(model.root);
    // The parts' raycast is disabled in batching.ts.
    this.proxy = new Mesh(new BoxGeometry(this.size.x, this.size.y, this.size.z), new MeshBasicMaterial({ visible: false }));
    this.proxy.position.y = this.size.y / 2;
    this.holder.add(this.proxy);

    // IWSDK builds a three-mesh-bvh BVH for every mesh under an interactable
    // entity, reordering the geometry's index in place. On a BatchedMesh that
    // scrambles every part's triangles (and it's wasted work: its raycast is
    // off). It skips geometries that already have one, so give them a stand-in.
    // Nor may pointers test them: the hand's grab sphere would fall back to
    // the model's bounding sphere and "touch" it from far away, taking the
    // trigger from the ray (so menu buttons wouldn't click).
    for (const batch of model.batches) {
      (batch.geometry as unknown as { boundsTree: unknown }).boundsTree = NO_BOUNDS_TREE;
      (batch as unknown as { pointerEvents: string }).pointerEvents = "none";
    }

    this.entity = world.createTransformEntity(this.holder, { persistent: true });
    this.entity.addComponent(RayInteractable);
    this.entity.addComponent(DistanceGrabbable, {
      movementMode: MovementMode.MoveFromTarget, // follows the ray
      scale: false, // the thumbsticks scale it (StickControl), not two rays
    });
  }

  get scale() {
    return this.holder.scale.x;
  }

  setScale(scale: number) {
    this.holder.scale.setScalar(Math.min(SCALE_MAX, Math.max(SCALE_MIN, scale)));
  }

  /** Turns it about the vertical through its base centre; positive is anticlockwise seen from above. */
  turn(angle: number) {
    this.holder.quaternion.premultiply(_turn.setFromAxisAngle(_up, angle));
  }

  /** Stands the model upright, keeping only its turn about the vertical. */
  upright() {
    _euler.setFromQuaternion(this.holder.quaternion, "YXZ");
    this.holder.quaternion.setFromAxisAngle(_up, _euler.y);
  }

  /** Upright, with its front (LDraw's front) towards `point`. */
  faceTowards(point: Vector3) {
    const dx = point.x - this.holder.position.x;
    const dz = point.z - this.holder.position.z;
    this.holder.quaternion.setFromAxisAngle(_up, Math.atan2(dx, dz));
  }

  realSize() {
    this.setScale(1);
    this.upright();
  }

  tabletop() {
    this.setScale(TABLETOP_SIZE / Math.max(this.size.x, this.size.y, this.size.z, 1e-3));
    this.upright();
  }

  /** Minifig scale, standing on the floor where it is. */
  walkIn() {
    this.setScale(WALK_IN_SCALE);
    this.upright();
    this.holder.position.y = 0;
  }

  /** Tabletop size, a little below eye level and ahead of the camera, facing it. */
  placeInFront(camera: { getWorldPosition(v: Vector3): Vector3; getWorldDirection(v: Vector3): Vector3 }) {
    camera.getWorldPosition(_head);
    camera.getWorldDirection(_forward);
    _forward.y = 0;
    if (_forward.lengthSq() < 1e-6) _forward.set(0, 0, -1);
    _forward.normalize();
    this.tabletop();
    this.holder.position.copy(_head).addScaledVector(_forward, 0.75);
    this.holder.position.y = Math.max(0.1, _head.y - 0.55);
    this.faceTowards(_head);
  }

  get grabbed() {
    return this.entity.hasComponent(Grabbed);
  }

  /** `hand`'s laser is on it (and not on the menu in front of it). */
  pointedAt(world: World, hand: Hand) {
    return world.input.multiPointers[hand].getPointer("ray").getIntersection()?.object === this.proxy;
  }

  /** A pointer is on it, or it's held. */
  get busy() {
    return this.entity.hasComponent(Hovered) || this.grabbed;
  }
}

/** Walkable ground for locomotion: the real floor (y = 0 in the local-floor space), invisible. */
export function createFloor(world: World): Entity {
  const floor = new Mesh(new PlaneGeometry(400, 400).rotateX(-Math.PI / 2), new MeshBasicMaterial({ visible: false }));
  const entity = world.createTransformEntity(floor, { persistent: true });
  entity.addComponent(LocomotionEnvironment, { type: "static" });
  return entity;
}

type Hand = "left" | "right";
const HANDS: Hand[] = ["left", "right"];
/** Nearer hits are ignored: the Quest's hit-test can hit your own hand or controller. */
const MIN_HIT_DISTANCE = 0.3;
const MAX_FLOOR_DISTANCE = 30;

const _origin = new Vector3();
const _direction = new Vector3();
const _floor = new Vector3();
const _quaternion = new Quaternion();

/**
 * One hand's placement pointer: a laser from the controller (or hand) to the
 * real surface it points at, and a ring there. The surface comes from the
 * headset's hit-test (tables, floor, walls...), or else from the floor plane.
 */
class SurfacePointer {
  readonly hit = new Vector3();
  hasHit = false;
  /** The ring and laser are showing: a trigger press (or pinch) now places the model. */
  aiming = false;
  private readonly probe: Entity;
  private readonly ring: Mesh;
  private readonly laser: Mesh;

  constructor(private readonly world: World, readonly hand: Hand) {
    // IWSDK moves this (invisible) object to the hit point and hides it when there's none.
    this.probe = world.createTransformEntity(new Group(), { persistent: true });
    this.probe.addComponent(EnvironmentRaycastTarget, { space: hand === "left" ? RaycastSpace.Left : RaycastSpace.Right });
    this.ring = new Mesh(
      new RingGeometry(0.05, 0.07, 48).rotateX(-Math.PI / 2), // flat: hit poses have +Y along the surface normal
      new MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.9 }),
    );
    this.laser = new Mesh(
      new CylinderGeometry(0.0025, 0.0025, 1, 8, 1, true).translate(0, 0.5, 0).rotateX(-Math.PI / 2), // 1 m along -Z
      new MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55, depthWrite: false }),
    );
    for (const mesh of [this.ring, this.laser]) {
      mesh.visible = false;
      (mesh as unknown as { pointerEvents: string }).pointerEvents = "none"; // never a pointer target itself
    }
    world.scene.add(this.ring);
    world.player.raySpaces[hand].add(this.laser); // follows the controller
  }

  update(connected: boolean, busy: boolean, floorY: number) {
    const space = this.world.player.raySpaces[this.hand];
    space.getWorldPosition(_origin);
    _direction.set(0, 0, -1).applyQuaternion(space.getWorldQuaternion(_quaternion));
    this.hasHit = false;
    const probe = this.probe.object3D;
    // Only a real hit-test result counts: the probe keeps its last (or initial)
    // place when there's none, e.g. before the hit-test source exists.
    const hitTestResult = this.probe.getValue(EnvironmentRaycastTarget, "xrHitTestResult");
    if (connected && probe && hitTestResult) {
      probe.getWorldPosition(this.hit);
      if (this.hit.distanceTo(_origin) >= MIN_HIT_DISTANCE) {
        this.hasHit = true;
        probe.getWorldQuaternion(this.ring.quaternion);
      }
    }
    if (connected && !this.hasHit && _direction.y < -0.02) {
      const t = (floorY - _origin.y) / _direction.y;
      if (t >= MIN_HIT_DISTANCE && t <= MAX_FLOOR_DISTANCE) {
        this.hit.copy(_origin).addScaledVector(_direction, t);
        this.ring.quaternion.identity();
        this.hasHit = true;
      }
    }
    this.aiming = this.hasHit && !busy;
    this.ring.visible = this.laser.visible = this.aiming;
    if (this.aiming) {
      const distance = this.hit.distanceTo(_origin);
      this.laser.scale.set(1, 1, distance);
      this.ring.position.copy(this.hit);
      this.ring.scale.setScalar(Math.min(3, Math.max(0.6, distance / 1.5))); // stays visible far away
    }
    setRayAlwaysVisible(this.world, this.hand, !this.aiming);
  }

  hide() {
    this.ring.visible = this.laser.visible = this.aiming = false;
  }
}

/** Thumbstick dead zone (sticks drift a little); full tilt is 1. */
const STICK_DEAD_ZONE = 0.2;
/** Full tilt up or down: the model doubles or halves in size every second. */
const SCALE_RATE = 2;
/** Full tilt left or right, radians per second. */
const TURN_RATE = Math.PI / 2;

/**
 * One hand's thumbstick on the model: point at it, then up or down scales it
 * (from its base, so it stays standing where it is), left or right turns it
 * clockwise or anticlockwise seen from above (the side facing you follows the
 * stick). Elsewhere the stick walks and turns you, as before (IWSDK's
 * locomotion).
 *
 * Who gets a push is decided when the stick leaves the centre, until it's back:
 * scaling down doesn't turn into walking once the shrinking model slips off the
 * laser, and sweeping the laser across the model doesn't stop you mid-walk.
 * Locomotion reads the sticks through input actions, so while this laser is on
 * the model (stick centred), or the model has the stick, this hand's stick
 * bindings are taken out: locomotion never sees the push (no stray snap
 * turns), and they only come back with the stick centred.
 */
class StickControl {
  private readonly bindings: InputActionBinding[];
  /** This hand's stick bindings are out: a push now goes to the model. */
  private detached = false;
  /** Who has the stick until it's back in the centre. */
  private owner: "model" | "locomotion" | null = null;

  constructor(private readonly world: World, readonly hand: Hand) {
    this.bindings = world.input.actions
      .getBindings()
      .filter(
        (b) => "handedness" in b && b.handedness === hand && "componentId" in b && b.componentId === InputComponent.Thumbstick,
      );
  }

  update(model: PlacedModel, delta: number) {
    const axes = this.world.input.xr.gamepads[this.hand]?.getAxesValues(InputComponent.Thumbstick);
    const x = stickValue(axes?.x ?? 0);
    const y = stickValue(axes?.y ?? 0);
    if (x === 0 && y === 0) this.owner = null;
    else this.owner ??= this.detached ? "model" : "locomotion";
    // Not while it's held: the grab sets its pose from the grab's start, every frame.
    if (this.owner === "model" && !model.grabbed) {
      const dt = Math.min(delta, 0.1); // a hitch doesn't make it jump
      if (Math.abs(y) >= Math.abs(x)) model.setScale(model.scale * SCALE_RATE ** (-y * dt)); // stick up is -y
      else model.turn(x * TURN_RATE * dt); // left: clockwise seen from above
    }
    this.detach(this.owner === "model" || (this.owner === null && model.pointedAt(this.world, this.hand)));
  }

  /** No model or no session: the stick is locomotion's again. */
  reset() {
    this.owner = null;
    this.detach(false);
  }

  private detach(detach: boolean) {
    if (detach === this.detached) return;
    this.detached = detach;
    const { actions } = this.world.input;
    for (const binding of this.bindings) {
      if (detach) actions.removeBinding(binding);
      else actions.addBinding(binding);
    }
  }
}

/** Past the dead zone, rescaled to 0..1 and squared: fine control near the centre. */
function stickValue(value: number) {
  const t = (Math.abs(value) - STICK_DEAD_ZONE) / (1 - STICK_DEAD_ZONE);
  return t > 0 ? Math.sign(value) * Math.min(1, t) ** 2 : 0;
}

/**
 * IWSDK's own ray (for the menu and grabbing) is only drawn while it touches
 * something. Keep it on, so you always see where each hand points, except
 * while the placement laser is showing instead. (No public setting for this:
 * it's the MultiPointer's ray visual.)
 */
function setRayAlwaysVisible(world: World, hand: Hand, always: boolean) {
  const visual = (world.input.multiPointers[hand] as unknown as { ray?: { visual?: { rayDisplayMode: RayDisplayMode } } })
    .ray?.visual;
  if (visual) visual.rayDisplayMode = always ? RayDisplayMode.Visible : RayDisplayMode.VisibleOnIntersection;
}

/**
 * Per-frame placement, for both hands: aim at a surface, trigger (or pinch)
 * to put the model there; and their thumbsticks on the model (StickControl).
 * Configured through `PlacementSystem.model`.
 */
export class PlacementSystem extends createSystem({}) {
  static model: PlacedModel | null = null;
  /** Frames to wait before the first placement, so the head pose is real. */
  static placeAfter = -1;
  /** After you put the model somewhere with the trigger (or a pinch). */
  static onPlaced: () => void = () => {};
  private pointers: SurfacePointer[] = [];
  private sticks: StickControl[] = [];
  private session: XRSession | undefined;
  private readonly selected = new Set<Hand>();
  private readonly onSelectStart = (event: XRInputSourceEvent) => {
    const hand = event.inputSource.handedness;
    if (hand === "left" || hand === "right") this.selected.add(hand);
  };

  init() {
    this.pointers = HANDS.map((hand) => new SurfacePointer(this.world, hand));
    this.sticks = HANDS.map((hand) => new StickControl(this.world, hand));
  }

  update(delta: number) {
    const model = PlacementSystem.model;
    const session = this.world.session;
    if (session !== this.session) {
      // Session select events: the same for controllers (trigger) and hands (pinch).
      this.session?.removeEventListener("selectstart", this.onSelectStart);
      session?.addEventListener("selectstart", this.onSelectStart);
      this.session = session;
      this.selected.clear();
    }
    if (!model || !session) {
      this.pointers.forEach((p) => p.hide());
      this.sticks.forEach((s) => s.reset());
      return;
    }
    if (PlacementSystem.placeAfter >= 0 && PlacementSystem.placeAfter-- === 0) {
      model.placeInFront(this.world.camera);
    }
    for (const stick of this.sticks) stick.update(model, delta);
    const floorY = this.world.player.getWorldPosition(_floor).y; // the real floor (locomotion moves it)
    for (const pointer of this.pointers) {
      const connected = !!this.world.input.getPrimaryInputSource(pointer.hand);
      // On the menu or the model, the trigger is for them: no placing.
      const busy = this.world.input.multiPointers[pointer.hand].getRayBusy() || model.grabbed;
      pointer.update(connected, busy, floorY);
      if (this.selected.has(pointer.hand) && pointer.aiming) {
        model.holder.position.copy(pointer.hit);
        model.faceTowards(this.world.camera.getWorldPosition(_origin));
        PlacementSystem.onPlaced();
      }
    }
    this.selected.clear();
  }
}
