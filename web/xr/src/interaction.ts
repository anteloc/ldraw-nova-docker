// Moving the model around in mixed reality, with IWSDK's built-ins:
//
// * Point at it (or reach inside) and hold the trigger (or pinch) to move and turn it from where
//   you are (DistanceGrabbable: IWSDK's near grabs don't take rays, far ones do).
// * Point at it and push that hand's thumbstick: up or down scales it, left or
//   right turns it, whether you're holding it or not (StickControl).
// * Point at a real table or floor with either hand and press the trigger (or
//   pinch) to put it there: a laser and a ring show where (SurfacePointer).
// * Presets: real LEGO size and tabletop.
// * X/A recovers the model at tabletop size, 75 cm along the current gaze.
// * Locomotion (thumbsticks, when not pointing at the model) over an invisible floor.
import {
  BoxGeometry,
  createSystem,
  CylinderGeometry,
  DistanceGrabbable,
  type Entity,
  EnvironmentRaycastTarget,
  Euler,
  Grabbed,
  GrabSystem,
  Group,
  Hovered,
  type InputActionBinding,
  InputComponent,
  LocomotionEnvironment,
  Matrix4,
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
import type { XRModel } from "./model";

/** Tabletop preset: the model's longest side, metres. */
const TABLETOP_SIZE = 0.6;
/** Smallest: real LEGO size. Any smaller is hard to find, and to point at and grab. */
const SCALE_MIN = 1;
/** A standing minifig, about 4 cm tall... */
const MINIFIG_HEIGHT = 0.04;
/** ...at its biggest, as tall as a person: ×43.75. */
const SCALE_MAX = 1.75 / MINIFIG_HEIGHT;
/** Controllers this close to the bounds target the model even when pointing out of it. */
const NEAR_MODEL_DISTANCE = 0.08;

/** Marks a geometry as having a BVH already (see PlacedModel). */
const NO_BOUNDS_TREE = Object.freeze({ placeholder: true });

const _up = new Vector3(0, 1, 0);
const _head = new Vector3();
const _forward = new Vector3();
const _euler = new Euler(0, 0, 0, "YXZ");
const _turn = new Quaternion();
const _modelCenter = new Vector3();

/** The model in the world: a holder whose origin is the centre of the model's base. */
export class PlacedModel {
  readonly holder = new Group();
  readonly entity: Entity;
  private readonly size: Vector3;
  /** What pointers and hands hit: a plain box, not the model's thousands of parts. */
  private readonly proxy: Mesh;

  constructor(private readonly world: World, private readonly model: XRModel) {
    const { bounds } = model;
    this.size = bounds.getSize(new Vector3());
    // Base centre at the holder's origin: placing puts the base on the surface,
    // and scaling grows the model up from it.
    model.root.position.set(-(bounds.min.x + bounds.max.x) / 2, -bounds.min.y, -(bounds.min.z + bounds.max.z) / 2);
    this.holder.name = "model";
    this.holder.add(model.root);
    this.proxy = new Mesh(new BoxGeometry(1, 1, 1), new MeshBasicMaterial({ visible: false }));
    this.syncBounds();
    this.holder.add(this.proxy);
    // Near/inside still uses the ray's trigger and capture, never the grab or
    // touch sphere (which would take the trigger away from distance grabbing).
    this.proxy.pointerEventsType = { allow: "ray" };
    this.proxy.geometry.computeBoundingBox();
    const raycast = this.proxy.raycast.bind(this.proxy);
    const inverse = new Matrix4();
    const localOrigin = new Vector3();
    const closest = new Vector3();
    this.proxy.raycast = (raycaster, hits) => {
      this.proxy.updateWorldMatrix(true, false);
      inverse.copy(this.proxy.matrixWorld).invert();
      localOrigin.copy(raycaster.ray.origin).applyMatrix4(inverse);
      this.proxy.geometry.boundingBox!.clampPoint(localOrigin, closest);
      closest.applyMatrix4(this.proxy.matrixWorld);
      if (closest.distanceToSquared(raycaster.ray.origin) <= NEAR_MODEL_DISTANCE ** 2) {
        // Capture at the controller, not the box's exit face: an inside grab
        // must not suddenly acquire a long lever arm. The tiny positive length
        // also gives the pointer a well-defined direction and capture plane.
        const distance = Math.max(0.001, raycaster.near);
        if (distance <= raycaster.far) {
          hits.push({
            distance,
            point: raycaster.ray.at(distance, new Vector3()),
            normal: raycaster.ray.direction.clone().negate().transformDirection(inverse),
            object: this.proxy,
          });
        }
        return;
      }
      raycast(raycaster, hits);
    };

    // IWSDK builds a three-mesh-bvh BVH for every mesh under an interactable
    // entity, reordering the geometry's index in place. On a BatchedMesh that
    // scrambles every part's triangles (and it's wasted work: its raycast is
    // off). It skips geometries that already have one, so give them a stand-in.
    // Nor may pointers test them: the hand's grab sphere would fall back to
    // the model's bounding sphere and "touch" it from far away, taking the
    // trigger from the ray (so menu buttons wouldn't click).
    model.root.traverse(object => {
      const mesh = object as Mesh;
      if (!mesh.geometry) return;
      (mesh.geometry as unknown as { boundsTree: unknown }).boundsTree = NO_BOUNDS_TREE;
      mesh.pointerEvents = "none";
      mesh.raycast = () => {};
    });

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

  /** Follow the current animated pose without moving the holder or its pivot. */
  syncBounds() {
    const { bounds, root } = this.model;
    bounds.getSize(this.size);
    bounds.getCenter(this.proxy.position).add(root.position);
    this.proxy.scale.copy(this.size).clampScalar(1e-5, Infinity);
    this.proxy.updateMatrixWorld(true);
  }

  /** Scales it from its base centre, by `factor`, within the limits (real size to minifig as tall as you), also while it's held. */
  scaleBy(factor: number) {
    this.setScale(this.scale * factor);
    this.keepWhileHeld();
  }

  setScale(scale: number) {
    this.holder.scale.setScalar(Math.min(SCALE_MAX, Math.max(SCALE_MIN, scale)));
  }

  /** Turns it about the vertical through its base centre; positive is anticlockwise seen from above (also while it's held). */
  turn(angle: number) {
    this.holder.quaternion.premultiply(_turn.setFromAxisAngle(_up, angle));
    this.keepWhileHeld();
  }

  // While it's held, the grab sets its pose every frame from the pose it was
  // grabbed with: start the grab over from here (as if grabbed like this), so
  // the new size or turn stays and it keeps following the ray. IWSDK doesn't
  // export its Handle component: find it by id (the grab system makes it).
  private keepWhileHeld() {
    if (!this.grabbed) return;
    const component = this.entity.getComponents().find((c) => c.id === "Handle");
    const handle = component && (this.entity.getValue(component, "instance" as never) as { save(): void } | undefined);
    handle?.save();
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

  /** About 60 cm across, within the scale limits: bigger models stay at real size, the tiniest grow only so far. */
  tabletop() {
    this.setScale(TABLETOP_SIZE / Math.max(this.size.x, this.size.y, this.size.z, 1e-3));
    this.upright();
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

  /** Recover even a lost or held model: Tabletop, centred 75 cm along the gaze. */
  recenter(camera: { getWorldPosition(v: Vector3): Vector3; getWorldDirection(v: Vector3): Vector3 }) {
    this.world.getSystem(GrabSystem)?.forceRelease(this.entity);
    camera.getWorldPosition(_head);
    camera.getWorldDirection(_forward).normalize();
    this.tabletop();
    this.holder.position.copy(_head).addScaledVector(_forward, 0.75);
    this.faceTowards(_head);
    // Animated parts can shift the centre away from the original base pivot.
    _modelCenter.copy(this.proxy.position).multiplyScalar(this.scale).applyQuaternion(this.holder.quaternion);
    this.holder.position.sub(_modelCenter);
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
/** A push starts here, before the dead zone ends: locomotion is held back before it would act. */
const STICK_PUSHED = 0.1;
/** How long a push that starts off the model waits for the laser to get there (aiming and pushing at once), ms. */
const AIM_GRACE_MS = 150;
/** Full tilt up or down: the model doubles or halves in size every second. */
const SCALE_RATE = 2;
/** Full tilt left or right, radians per second. */
const TURN_RATE = Math.PI / 2;

/**
 * One hand's thumbstick on the model: point at it (holding it or not), then up
 * or down scales it (from its base, so it stays standing where it is), left or
 * right turns it clockwise or anticlockwise seen from above (the side facing
 * you follows the stick). Elsewhere the stick walks and turns you, as before
 * (IWSDK's locomotion).
 *
 * Who gets a push is decided when it starts, until the stick is back in the
 * centre: scaling down doesn't turn into walking once the shrinking model
 * slips off the laser, and sweeping the laser across the model doesn't stop
 * you mid-walk. A push that starts off the model waits a moment (AIM_GRACE)
 * for the laser to get there, since people aim and push at once. And a push
 * does one thing, whichever it starts as: a turn that drifts towards
 * diagonal doesn't start scaling.
 *
 * Locomotion reads the sticks through input actions, so while this laser is
 * on the model (stick centred), or the push is the model's or still waiting,
 * this hand's stick bindings are taken out: locomotion never sees the push (no
 * stray snap turns). A push that turns out to be locomotion's gets them back
 * and goes on as usual. That's decided in claim(), just before the actions
 * read the sticks each frame, so it holds from a push's first frame.
 */
class StickControl {
  private readonly bindings: InputActionBinding[];
  /** This hand's stick bindings are out: a push now goes to the model. */
  private detached = false;
  /** Who has the stick until it's back in the centre ("waiting": for the laser to reach the model). */
  private owner: "model" | "locomotion" | "waiting" | null = null;
  private waitingSince = 0;
  /** What the model's push does, chosen when it first acts. */
  private action: "scale" | "turn" | null = null;
  private suspended = false;

  constructor(private readonly world: World, readonly hand: Hand) {
    this.bindings = world.input.actions
      .getBindings()
      .filter(
        (b) => "handedness" in b && b.handedness === hand && "componentId" in b && b.componentId === InputComponent.Thumbstick,
      );
  }

  /** Each frame, before the input actions read the sticks (this frame's sticks and pointers are in): who has the stick. */
  claim(model: PlacedModel) {
    const { x, y } = this.stick();
    if (this.suspended) {
      if (Math.max(Math.abs(x), Math.abs(y)) >= STICK_PUSHED) return;
      this.suspended = false;
    }
    const pointed = model.pointedAt(this.world, this.hand);
    if (Math.max(Math.abs(x), Math.abs(y)) < STICK_PUSHED) {
      this.owner = this.action = null;
    } else if (this.owner === null) {
      this.owner = this.detached ? "model" : "waiting";
      this.waitingSince = performance.now();
    }
    if (this.owner === "waiting") {
      if (pointed) this.owner = "model";
      else if (performance.now() - this.waitingSince >= AIM_GRACE_MS) this.owner = "locomotion"; // gets it, a moment late
    }
    this.detach(this.owner === "model" || this.owner === "waiting" || (this.owner === null && pointed));
  }

  /** Each frame, with the systems: the model's push scales or turns it. */
  update(model: PlacedModel, delta: number) {
    if (this.owner !== "model") return;
    const dt = Math.min(delta, 0.1); // a hitch doesn't make it jump
    const { x: rawX, y: rawY } = this.stick();
    const x = stickValue(rawX);
    const y = stickValue(rawY);
    if (x === 0 && y === 0) return;
    this.action ??= Math.abs(y) >= Math.abs(x) ? "scale" : "turn";
    if (this.action === "scale" && y !== 0) model.scaleBy(SCALE_RATE ** (-y * dt)); // stick up is -y
    if (this.action === "turn" && x !== 0) model.turn(x * TURN_RATE * dt); // left: clockwise seen from above
  }

  /** No model or no session: the stick is locomotion's again. */
  reset() {
    this.suspended = false;
    this.owner = this.action = null;
    this.detach(false);
  }

  /** Recovery cancels the old gesture; a fresh push starts after the stick centres. */
  suspendUntilCentered() {
    this.owner = this.action = null;
    this.suspended = true;
    this.detach(true);
  }

  private stick() {
    const axes = this.world.input.xr.gamepads[this.hand]?.getAxesValues(InputComponent.Thumbstick);
    return { x: axes?.x ?? 0, y: axes?.y ?? 0 }; // none with hand tracking
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
    // Claim the sticks just before IWSDK's input actions read them (input
    // manager: gamepads and pointers, then actions), so locomotion only ever
    // sees its own pushes, from their first frame.
    const { actions } = this.world.input;
    const update = actions.update.bind(actions);
    actions.update = (context) => {
      const model = PlacementSystem.model;
      for (const stick of this.sticks) {
        if (model && this.world.session) stick.claim(model);
        else stick.reset();
      }
      update(context);
    };
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
      return;
    }
    const { left, right } = this.world.input.xr.gamepads;
    if (left?.getButtonDown(InputComponent.X_Button) || right?.getButtonDown(InputComponent.A_Button)) {
      PlacementSystem.placeAfter = -1;
      model.recenter(this.world.camera);
      this.sticks.forEach((stick) => stick.suspendUntilCentered());
      this.pointers.forEach((pointer) => pointer.hide());
      this.selected.clear();
      PlacementSystem.onPlaced();
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
      const busy = model.pointedAt(this.world, pointer.hand)
        || this.world.input.multiPointers[pointer.hand].getRayBusy() || model.grabbed;
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
