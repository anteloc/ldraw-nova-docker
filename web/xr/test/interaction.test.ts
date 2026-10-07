import { Box3, BoxGeometry, Group, Mesh, MeshBasicMaterial, PerspectiveCamera, Scene, Vector3 } from "three";
import { type Entity, Grabbed, InputComponent, type World } from "@iwsdk/core";
import { HandleStore } from "@pmndrs/handle";
import { createRayPointer } from "@pmndrs/pointer-events";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { BatchedModel } from "../src/batching";
import { PlacedModel, PlacementSystem } from "../src/interaction";

// Real ray/capture/handle math, with only the ECS and physical XR devices stubbed.
// MoveFromTarget delegates to this HandleStore with these options in IWSDK.
function setup(size = new Vector3(0.2, 0.3, 0.4)) {
  const scene = new Scene();
  const camera = new PerspectiveCamera();
  camera.position.set(0, 1.6, 0);
  const spaces = { left: new Group(), right: new Group() };
  scene.add(camera, spaces.left, spaces.right);
  const pointers = {
    left: createRayPointer(() => camera, { current: spaces.left }, {}),
    right: createRayPointer(() => camera, { current: spaces.right }, {}),
  };
  const axes = { left: { x: 0, y: 0 }, right: { x: 0, y: 0 } };
  const buttons = { left: new Set<string>(), right: new Set<string>() };
  const gamepad = (hand: "left" | "right") => ({
    getAxesValues: () => axes[hand],
    getButtonDown: (button: string) => buttons[hand].has(button),
  });
  const multiPointer = (hand: "left" | "right") => ({
    getPointer: () => pointers[hand],
    getRayBusy: () => {
      const hit = pointers[hand].getIntersection();
      return !!hit && !(hit.object as { isVoidObject?: boolean }).isVoidObject;
    },
  });
  type Component = ReturnType<Entity["getComponents"]>[number];
  const createEntity = (object3D = new Group()) => {
    scene.add(object3D);
    const components = new Map<Component, Record<string, unknown>>();
    return {
      object3D,
      addComponent: (c: Component, values = {}) => components.set(c, values),
      removeComponent: (c: Component) => components.delete(c),
      hasComponent: (c: Component) => components.has(c),
      getComponents: () => [...components.keys()],
      getValue: (c: Component, key: string) => components.get(c)?.[key],
    } as unknown as Entity;
  };
  const bindings = ["left", "right"].map((handedness) => ({ handedness, componentId: InputComponent.Thumbstick }));
  const actions = { getBindings: () => bindings, addBinding: vi.fn(), removeBinding: vi.fn(), update: vi.fn() };
  const forceRelease = vi.fn(() => handle.cancel());
  const session = new EventTarget();
  const world = {
    scene, camera, session,
    player: Object.assign(new Group(), { raySpaces: spaces }),
    createTransformEntity: createEntity,
    getSystem: () => ({ forceRelease }),
    input: {
      actions,
      getPrimaryInputSource: () => ({}),
      xr: { gamepads: { left: gamepad("left"), right: gamepad("right") } },
      multiPointers: { left: multiPointer("left"), right: multiPointer("right") },
    },
  } as unknown as World;
  const model = new PlacedModel(world, {
    root: new Group(), batches: [], bounds: new Box3(new Vector3(), size),
  } as unknown as BatchedModel);
  const handle = new HandleStore(model.holder, () => ({ projectRays: false, scale: false }));
  handle.bind(model.holder);
  model.entity.addComponent({ id: "Handle" } as Component, { instance: handle });
  let time = 0;
  const move = () => {
    scene.updateMatrixWorld(true);
    for (const pointer of Object.values(pointers)) pointer.move(scene, { timeStamp: ++time });
    handle.update(time);
    if (handle.inputState.size) model.entity.addComponent(Grabbed);
    else model.entity.removeComponent(Grabbed);
  };
  const press = (hand: "left" | "right") => {
    pointers[hand].down({ button: 0, timeStamp: ++time });
    move();
  };
  PlacementSystem.model = model;
  const system = new PlacementSystem(world, undefined as never, 0);
  system.init();
  const frame = () => {
    move();
    world.input.actions.update({} as never);
    system.update(0.1);
    buttons.left.clear();
    buttons.right.clear();
  };
  return { model, scene, world, camera, spaces, pointers, axes, buttons, actions, forceRelease, handle, session, move, press, frame };
}

function expectVector(actual: Vector3, expected: Vector3) {
  expect(actual.distanceTo(expected)).toBeLessThan(1e-7);
}

afterEach(() => {
  PlacementSystem.model = null;
  PlacementSystem.placeAfter = -1;
  PlacementSystem.onPlaced = () => {};
});

describe("close-range model targeting", () => {
  it.each(["left", "right"] as const)("grabs from inside with %s without jumping, then follows the controller", (hand) => {
    const { model, world, spaces, pointers, handle, move, press } = setup();
    spaces[hand].position.set(0, 0.15, 0);
    move();
    expect(model.pointedAt(world, hand)).toBe(true);
    expect(pointers[hand].getIntersection()!.distance).toBeCloseTo(0.001);
    const before = model.holder.position.clone();
    press(hand);
    expect(handle.inputState.size).toBe(1);
    expectVector(model.holder.position, before);
    spaces[hand].position.x += 0.1;
    move();
    expectVector(model.holder.position, before.add(new Vector3(0.1, 0, 0)));
    pointers[hand].up({ button: 0, timeStamp: 100 });
    move();
    expect(handle.inputState.size).toBe(0);
  });

  it("uses an 8 cm world-space margin on rotated, scaled bounds, even looking away", () => {
    const { model, world, spaces, move } = setup();
    model.setScale(5);
    model.holder.position.set(2, 1, -3);
    model.holder.rotation.y = Math.PI / 2;
    // The local +X side is world -Z after the quarter turn.
    spaces.left.position.set(2, 1.5, -3.57);
    move();
    expect(model.pointedAt(world, "left")).toBe(true);
    spaces.left.position.z = -3.59;
    move();
    expect(model.pointedAt(world, "left")).toBe(false);
  });

  it("keeps distant ray targeting and gives menu UI priority even from inside", () => {
    const { model, world, scene, spaces, pointers, move } = setup();
    spaces.left.position.set(0, 0.15, 2);
    move();
    expect(pointers.left.getIntersection()!.distance).toBeCloseTo(1.8);
    spaces.left.position.z = 0;
    const menu = new Mesh(new BoxGeometry(0.1, 0.1, 0.01), new MeshBasicMaterial());
    menu.position.set(0, 0.15, -0.5);
    menu.pointerEvents = "auto";
    menu.pointerEventsOrder = 1;
    scene.add(menu);
    move();
    expect(pointers.left.getIntersection()!.object).toBe(menu);
    expect(model.pointedAt(world, "left")).toBe(false);
  });

  it("routes sticks to resize and rotate from inside, including while grabbed", () => {
    const { model, spaces, axes, actions, press, frame } = setup();
    spaces.left.position.set(0, 0.15, 0);
    frame();
    axes.left.y = -1;
    frame();
    expect(model.scale).toBeGreaterThan(1);
    expect(actions.removeBinding).toHaveBeenCalled();
    axes.left.y = 0;
    frame();
    press("left");
    axes.left.x = 1;
    frame();
    expect(model.holder.rotation.y).toBeGreaterThan(0);
    const rotated = model.holder.quaternion.clone();
    axes.left.x = 0;
    frame();
    expect(model.holder.quaternion.angleTo(rotated)).toBeLessThan(1e-7);
  });

  it("does not place the model on the floor when the trigger starts inside it", () => {
    const { model, spaces, session, frame } = setup();
    spaces.left.position.set(0, 0.15, 0);
    spaces.left.rotation.x = -Math.PI / 4;
    frame(); // register the XR session listener
    const onPlaced = PlacementSystem.onPlaced = vi.fn();
    session.dispatchEvent(Object.assign(new Event("selectstart"), { inputSource: { handedness: "left" } }));
    frame();
    expectVector(model.holder.position, new Vector3());
    expect(onPlaced).not.toHaveBeenCalled();
  });
});

describe("recenter recovery", () => {
  it.each([
    ["left", InputComponent.X_Button], ["right", InputComponent.A_Button],
  ] as const)("recovers with %s %s and waits for a held stick to centre", (hand, button) => {
    const { model, camera, spaces, axes, buttons, forceRelease, handle, press, frame } = setup();
    spaces[hand].position.set(0, 0.15, 0);
    frame();
    press(hand);
    axes[hand].y = -1;
    frame();
    camera.position.set(4, 1.7, -2);
    camera.rotation.set(-0.3, 0.8, 0);
    buttons[hand].add(button);
    frame();
    expect(forceRelease).toHaveBeenCalledWith(model.entity);
    expect(handle.inputState.size).toBe(0);
    expect(model.scale).toBeCloseTo(1.5); // 0.6 m / 0.4 m
    const centre = model.holder.position.clone().add(new Vector3(0, 0.3 * model.scale / 2, 0));
    expectVector(centre, camera.getWorldPosition(new Vector3()).addScaledVector(camera.getWorldDirection(new Vector3()), 0.75));
    const recovered = model.holder.position.clone();
    spaces[hand].position.set(20, -3, 9);
    frame();
    frame();
    expect(model.scale).toBeCloseTo(1.5);
    expectVector(model.holder.position, recovered);
    axes[hand].y = 0;
    spaces[hand].position.copy(centre);
    frame();
    axes[hand].y = -1;
    frame();
    expect(model.scale).toBeGreaterThan(1.5);
  });

  it.each([0.002, 0.4, 2])("uses the same Tabletop limits for a %s m lost model", (side) => {
    const { model, camera } = setup(new Vector3(side, side, side));
    model.tabletop();
    const tabletop = model.scale;
    model.setScale(40);
    model.holder.position.set(100, -50, 20);
    model.holder.rotation.set(1, 2, 3);
    model.recenter(camera);
    expect(model.scale).toBe(tabletop);
    expectVector(new Vector3(0, 1, 0).applyQuaternion(model.holder.quaternion), new Vector3(0, 1, 0));
    expectVector(model.holder.position.clone().add(new Vector3(0, side * tabletop / 2, 0)), new Vector3(0, 1.6, -0.75));
  });
});
