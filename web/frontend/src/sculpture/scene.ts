/** Manual editor rendering adapted from BrickBuilderAI VoxelViewer (MIT, 220f3fe).
 * Retains instanced stud geometry, brick-height coordinates and face editing;
 * Nova owns persistence, palette and controls. See LICENSE.brickbuilder.
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import type { Cell, EditTool } from "./cells";

export class SculptureScene {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(45, 1, .1, 2000);
  private controls: OrbitControls;
  private group = new THREE.Group();
  private mesh: THREE.InstancedMesh | null = null;
  private geometry: THREE.BufferGeometry;
  private material = new THREE.MeshStandardMaterial({ roughness: .3 });
  private observer: ResizeObserver;
  private palette = new Map<number, string>();
  private tool: EditTool = "orbit";
  private pointer = { x: 0, y: 0 };
  private fitted = false;
  private pointers = new Set<number>();
  private gesture = false;

  constructor(host: HTMLElement, private onPick: (index: number, normal: number[]) => void) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(0xf3f4f6);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    const box = new THREE.BoxGeometry(1, 1, 1.2);
    const stud = new THREE.CylinderGeometry(.3, .3, .22, 16);
    stud.rotateX(Math.PI / 2); stud.translate(0, 0, .71);
    this.geometry = mergeGeometries([box, stud])!;
    box.dispose(); stud.dispose();
    this.group.rotation.x = -Math.PI / 2;
    this.scene.add(this.group, new THREE.HemisphereLight(0xffffff, 0x667788, 2.4));
    const light = new THREE.DirectionalLight(0xffffff, 3); light.position.set(20, 40, 30); this.scene.add(light);
    const fill = new THREE.DirectionalLight(0xffffff, 1.5); fill.position.set(-20, 10, -30); this.scene.add(fill);
    host.append(this.renderer.domElement);
    this.renderer.domElement.setAttribute("aria-label", "Interactive sculpture. Choose Add, Paint or Erase, then click a cell.");
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.observer = new ResizeObserver(() => {
      this.camera.aspect = host.clientWidth / Math.max(1, host.clientHeight); this.camera.updateProjectionMatrix();
      this.renderer.setSize(host.clientWidth, host.clientHeight);
    });
    this.observer.observe(host);
    this.renderer.domElement.addEventListener("pointerdown", this.down);
    this.renderer.domElement.addEventListener("pointerup", this.up);
    this.renderer.domElement.addEventListener("pointercancel", this.cancel);
    this.renderer.domElement.addEventListener("contextmenu", this.context);
    this.renderer.setAnimationLoop(() => { this.controls.update(); this.renderer.render(this.scene, this.camera); });
  }
  private context = (e: Event) => e.preventDefault();
  private cancel = (e: PointerEvent) => { this.pointers.delete(e.pointerId); };
  private down = (e: PointerEvent) => {
    if (!this.pointers.size) this.gesture = false;
    this.pointers.add(e.pointerId);
    if (this.pointers.size > 1) this.gesture = true;
    this.pointer = { x: e.clientX, y: e.clientY };
  };
  private up = (e: PointerEvent) => {
    this.pointers.delete(e.pointerId);
    if (this.gesture || this.tool === "orbit" || e.button !== 0 || Math.hypot(e.clientX - this.pointer.x, e.clientY - this.pointer.y) > 6 || !this.mesh) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((e.clientX - rect.left) / rect.width * 2 - 1, -(e.clientY - rect.top) / rect.height * 2 + 1), this.camera);
    const hit = ray.intersectObject(this.mesh)[0];
    if (hit?.instanceId !== undefined && hit.face) this.onPick(hit.instanceId, hit.face.normal.toArray());
  };
  setTool(tool: EditTool) {
    this.tool = tool;
    this.controls.mouseButtons.LEFT = tool === "orbit" ? THREE.MOUSE.ROTATE : null as unknown as THREE.MOUSE;
    this.controls.mouseButtons.RIGHT = THREE.MOUSE.ROTATE;
    this.controls.touches.ONE = tool === "orbit" ? THREE.TOUCH.ROTATE : null as unknown as THREE.TOUCH;
    this.renderer.domElement.style.cursor = tool === "orbit" ? "grab" : "crosshair";
  }
  update(cells: Cell[], palette: { code: number; hex: string }[]) {
    this.palette = new Map(palette.map(c => [c.code, c.hex]));
    if (this.mesh) { this.group.remove(this.mesh); this.mesh.dispose(); }
    this.mesh = new THREE.InstancedMesh(this.geometry, this.material, cells.length);
    const matrix = new THREE.Matrix4();
    cells.forEach(([x, y, z, code], i) => {
      this.mesh!.setMatrixAt(i, matrix.makeTranslation(x, y, z * 1.2));
      this.mesh!.setColorAt(i, new THREE.Color(this.palette.get(code) || "#888888"));
    });
    this.mesh.computeBoundingSphere(); this.group.add(this.mesh);
    if (!this.fitted) { this.fit(); this.fitted = true; }
  }
  fit() {
    this.group.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(this.group);
    const centre = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const distance = Math.max(size.x, size.y, size.z, 4) * 1.8 / Math.min(1, this.camera.aspect);
    this.controls.target.copy(centre);
    this.camera.position.copy(centre).add(new THREE.Vector3(distance * .35, distance * .3, distance));
    this.camera.far = Math.max(2000, distance * 5); this.camera.updateProjectionMatrix(); this.controls.update();
  }
  dispose() {
    this.observer.disconnect(); this.renderer.setAnimationLoop(null);
    this.renderer.domElement.removeEventListener("pointerdown", this.down);
    this.renderer.domElement.removeEventListener("pointerup", this.up);
    this.renderer.domElement.removeEventListener("pointercancel", this.cancel);
    this.renderer.domElement.removeEventListener("contextmenu", this.context);
    this.controls.dispose(); this.mesh?.dispose(); this.geometry.dispose(); this.material.dispose(); this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
