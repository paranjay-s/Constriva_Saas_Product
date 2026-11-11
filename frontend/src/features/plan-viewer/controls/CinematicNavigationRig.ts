// frontend/src/features/plan-viewer/controls/CinematicNavigationRig.ts
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { ProximityDoorNode } from '../builders/buildOpenings';

export type CameraNavMode = 'orbit' | 'walkthrough' | 'drone' | 'arrival';

export interface NavRigOptions {
  container: HTMLElement;
  camera: THREE.PerspectiveCamera;
  doors: ProximityDoorNode[];
  onModeChange?: (mode: CameraNavMode) => void;
  onCeilingUpdate?: (cameraY: number) => void;
  onRequestRender: () => void;
}

export class CinematicNavigationRig {
  public mode: CameraNavMode = 'orbit';
  public camera: THREE.PerspectiveCamera;
  public controls: OrbitControls;
  public doors: ProximityDoorNode[] = [];
  public targetFov = 30;

  private container: HTMLElement;
  private onRequestRender: () => void;
  private onModeChange?: (mode: CameraNavMode) => void;
  private onCeilingUpdate?: (cameraY: number) => void;

  // Animation Tween State
  private isTweening = false;
  private tweenProgress = 0;
  private tweenDuration = 1.6;
  private tweenStartPos = new THREE.Vector3();
  private tweenTargetPos = new THREE.Vector3();
  private tweenStartLook = new THREE.Vector3();
  private tweenTargetLook = new THREE.Vector3();
  private onTweenComplete?: () => void;

  // Spline Drone Tour State
  private tourCurve: THREE.CatmullRomCurve3 | null = null;
  private tourProgress = 0;
  private isTouring = false;

  // Walkthrough Keys & Mouse State
  private keysDown: Record<string, boolean> = {};
  private isMouseDown = false;
  private prevMouseX = 0;
  private prevMouseY = 0;
  private yaw = 0;
  private pitch = 0;

  constructor(opts: NavRigOptions) {
    this.container = opts.container;
    this.camera = opts.camera;
    this.doors = opts.doors;
    this.onRequestRender = opts.onRequestRender;
    this.onModeChange = opts.onModeChange;
    this.onCeilingUpdate = opts.onCeilingUpdate;

    this.controls = new OrbitControls(this.camera, this.container);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.maxPolarAngle = 1.38;
    this.controls.minPolarAngle = 0.05;

    this.setupEventListeners();
  }

  private setupEventListeners() {
    window.addEventListener('keydown', (e) => {
      this.keysDown[e.code] = true;

      // ESC key immediately halts drone tour or exits walkthrough to aerial view
      if (e.code === 'Escape') {
        if (this.mode === 'drone' || this.isTouring) {
          this.stopTour();
        } else if (this.mode === 'walkthrough') {
          this.setMode('orbit');
        }
      }

      if (this.mode === 'walkthrough') {
        this.onRequestRender();
      }
    });

    window.addEventListener('keyup', (e) => {
      this.keysDown[e.code] = false;
    });

    this.container.addEventListener('mousedown', (e) => {
      this.isMouseDown = true;
      this.prevMouseX = e.clientX;
      this.prevMouseY = e.clientY;
    });

    window.addEventListener('mouseup', () => {
      this.isMouseDown = false;
    });

    this.container.addEventListener('mousemove', (e) => {
      if (this.mode === 'walkthrough' && this.isMouseDown) {
        const dx = e.clientX - this.prevMouseX;
        const dy = e.clientY - this.prevMouseY;
        this.prevMouseX = e.clientX;
        this.prevMouseY = e.clientY;

        this.yaw -= dx * 0.0035;
        // Expanded vertical pitch range (-82.5° to +82.5°) so user can look straight down at floor or up at ceiling
        this.pitch = Math.max(-1.44, Math.min(1.44, this.pitch - dy * 0.0035));
        this.updateFpvLook();
        this.onRequestRender();
      }
    });

    // Mouse wheel in walkthrough: smoothly glide forward/backward along viewing angle
    this.container.addEventListener(
      'wheel',
      (e) => {
        if (this.mode === 'walkthrough') {
          e.preventDefault();
          const forward = new THREE.Vector3(
            Math.sin(this.yaw),
            0,
            -Math.cos(this.yaw)
          ).normalize();
          const moveStep = (e.deltaY > 0 ? -1 : 1) * 0.45;
          this.camera.position.addScaledVector(forward, moveStep);
          this.camera.position.y = 1.50; // Comfortable eye level
          this.updateFpvLook();
          this.onRequestRender();
        }
      },
      { passive: false }
    );
  }

  private updateFpvLook() {
    const dir = new THREE.Vector3(
      Math.sin(this.yaw) * Math.cos(this.pitch),
      Math.sin(this.pitch),
      -Math.cos(this.yaw) * Math.cos(this.pitch)
    );
    const target = this.camera.position.clone().add(dir);
    this.camera.lookAt(target);
    this.controls.target.copy(target);
  }

  /**
   * Smoothly animates camera to target eye level and look target
   */
  public animateTo(
    targetPos: THREE.Vector3,
    targetLook: THREE.Vector3,
    duration = 1.6,
    onComplete?: () => void
  ) {
    this.isTweening = true;
    this.tweenProgress = 0;
    this.tweenDuration = duration;
    this.tweenStartPos.copy(this.camera.position);
    this.tweenTargetPos.copy(targetPos);
    this.tweenStartLook.copy(this.controls.target);
    this.tweenTargetLook.copy(targetLook);
    this.onTweenComplete = onComplete;
    this.onRequestRender();
  }

  /**
   * Welcomes visitor: glides from entrance gate, through opening door into living room foyer
   */
  public playWelcomeArrival(frontDoorPos: THREE.Vector3, foyerPos: THREE.Vector3) {
    this.setMode('arrival');
    this.targetFov = 75; // Wide architectural angle
    // Start 7m in front of entrance at human eye level
    this.camera.position.set(frontDoorPos.x, 1.55, frontDoorPos.z + 7.0);
    this.controls.target.copy(frontDoorPos);

    this.animateTo(
      new THREE.Vector3(foyerPos.x, 1.50, foyerPos.z),
      new THREE.Vector3(foyerPos.x, 1.50, foyerPos.z - 4),
      3.2,
      () => {
        // After showing living room, pull up smoothly into isometric dollhouse
        this.animateTo(
          new THREE.Vector3(foyerPos.x + 12, 14, foyerPos.z + 16),
          foyerPos,
          2.0,
          () => {
            this.setMode('orbit');
          }
        );
      }
    );
  }

  /**
   * Teleports camera into room at human eye-level (1.50m) with wide-angle FOV (75°) for expansive 360 inspection
   */
  public teleportToRoom(centroid: THREE.Vector3, lookAt?: THREE.Vector3) {
    this.setMode('walkthrough');
    this.targetFov = 75; // Enscape ultra-wide architectural angle (18mm equivalent)
    const eyeLevelPos = new THREE.Vector3(centroid.x, 1.50, centroid.z);
    const targetLook = lookAt || new THREE.Vector3(centroid.x, 1.50, centroid.z - 2.5);

    this.animateTo(eyeLevelPos, targetLook, 1.4, () => {
      this.yaw = 0;
      this.pitch = 0;
      this.updateFpvLook();
    });
  }

  /**
   * Starts Higgsfield-quality automated drone tour through rooms with speed ramping
   */
  public startDroneTour(waypoints: THREE.Vector3[]) {
    if (waypoints.length < 2) return;
    this.setMode('drone');
    this.targetFov = 72; // Wide aerial drone lens
    this.tourCurve = new THREE.CatmullRomCurve3(waypoints, true, 'catmullrom', 0.15);
    this.tourProgress = 0;
    this.isTouring = true;
    this.onRequestRender();
  }

  public stopTour() {
    this.isTouring = false;
    this.setMode('orbit');
  }

  public setMode(mode: CameraNavMode) {
    this.mode = mode;
    this.controls.enabled = mode === 'orbit';
    if (mode === 'orbit') {
      this.targetFov = 30; // Clean isometric perspective
    } else if (mode === 'walkthrough') {
      this.targetFov = 75; // Ultra-wide interior walkthrough
    } else if (mode === 'drone') {
      this.targetFov = 72;
    } else if (mode === 'arrival') {
      this.targetFov = 75;
    }
    this.onModeChange?.(mode);
    this.onRequestRender();
  }

  /**
   * Frame update: handles WASD locomotion, drone speed ramping & door proximity sensing
   */
  public update(delta = 0.016): boolean {
    let active = false;

    // Smoothly lerp camera FOV to target lens (e.g. 30° in orbit -> 75° in room walkthrough)
    if (Math.abs(this.camera.fov - this.targetFov) > 0.05) {
      this.camera.fov = THREE.MathUtils.lerp(this.camera.fov, this.targetFov, 0.12);
      this.camera.updateProjectionMatrix();
      active = true;
    }

    // 1. Camera Tweening
    if (this.isTweening) {
      active = true;
      this.tweenProgress += delta / this.tweenDuration;
      const t = Math.min(1.0, this.tweenProgress);
      // Smooth cubic ease-in-out
      const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

      this.camera.position.lerpVectors(this.tweenStartPos, this.tweenTargetPos, ease);
      const look = new THREE.Vector3().lerpVectors(this.tweenStartLook, this.tweenTargetLook, ease);
      this.controls.target.copy(look);
      this.camera.lookAt(look);

      if (t >= 1.0) {
        this.isTweening = false;
        this.onTweenComplete?.();
      }
    }

    // 2. Automated Drone Spline Tour
    if (this.isTouring && this.tourCurve) {
      active = true;
      // Speed ramping: faster through doorways (2.2x), slower in rooms (0.4x)
      const currentPos = this.tourCurve.getPointAt(this.tourProgress % 1.0);
      const isNearDoor = this.doors.some((d) => d.worldPos.distanceTo(currentPos) < 2.0);
      const speedMult = isNearDoor ? 2.2 : 0.45;

      this.tourProgress += delta * 0.035 * speedMult;
      const nextT = (this.tourProgress) % 1.0;
      const lookAheadT = (this.tourProgress + 0.03) % 1.0;

      const pos = this.tourCurve.getPointAt(nextT);
      const look = this.tourCurve.getPointAt(lookAheadT);

      // Subtle banking roll (up to +-7 deg) on curve turns
      const tangent = this.tourCurve.getTangentAt(nextT);
      const bankAngle = THREE.MathUtils.clamp(-tangent.x * 0.12, -0.12, 0.12);

      this.camera.position.set(pos.x, 1.50, pos.z);
      this.camera.lookAt(look.x, 1.50, look.z);
      this.camera.rotation.z = bankAngle;
      this.controls.target.copy(look);
    }

    // 3. First-Person Walkthrough Movement (WASD + Arrows)
    if (this.mode === 'walkthrough' && !this.isTweening) {
      const moveSpeed = 3.6 * delta;
      const forward = new THREE.Vector3(Math.sin(this.yaw), 0, -Math.cos(this.yaw)).normalize();
      const right = new THREE.Vector3(Math.cos(this.yaw), 0, Math.sin(this.yaw)).normalize();

      const move = new THREE.Vector3();
      if (this.keysDown['KeyW'] || this.keysDown['ArrowUp']) move.add(forward);
      if (this.keysDown['KeyS'] || this.keysDown['ArrowDown']) move.sub(forward);
      if (this.keysDown['KeyD'] || this.keysDown['ArrowRight']) move.add(right);
      if (this.keysDown['KeyA'] || this.keysDown['ArrowLeft']) move.sub(right);

      if (move.lengthSq() > 0) {
        active = true;
        move.normalize().multiplyScalar(moveSpeed);
        this.camera.position.add(move);
        // Fixed comfortable eye level
        this.camera.position.y = 1.50;
        this.updateFpvLook();
      }
    }

    // 4. Update Orbit Controls in orbit mode
    if (this.mode === 'orbit' && !this.isTweening) {
      const controlsChanged = this.controls.update();
      if (controlsChanged) active = true;
    }

    // 5. Smart Ceiling Auto-Cull Notification
    this.onCeilingUpdate?.(this.camera.position.y);

    return active;
  }

  public dispose() {
    this.controls.dispose();
  }
}

