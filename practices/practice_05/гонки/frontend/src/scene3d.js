// 3D-сцена гонки на Three.js.
// Физика остаётся в App.vue: сюда приходят только x, y, angle каждой машинки (в координатах
// прежнего 2D-холста). Здесь они переводятся в мировые координаты и рисуются.
import {
  AmbientLight,
  BoxGeometry,
  BufferGeometry,
  CanvasTexture,
  Color,
  CylinderGeometry,
  DirectionalLight,
  DoubleSide,
  Float32BufferAttribute,
  Group,
  HemisphereLight,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  NearestFilter,
  PerspectiveCamera,
  PlaneGeometry,
  Scene,
  Sprite,
  SpriteMaterial,
  WebGLRenderer,
} from "three";

// Цвета (палитра из AGENTS.md)
const COLOR_BACKGROUND = 0x0d0a1f;
const COLOR_ROAD = 0x2a1b55;
const COLOR_CURB_INNER = 0x22d3ee; // внутренний бордюр, как в прежней 2D-трассе
const COLOR_CURB_OUTER = 0x8b5cf6; // внешний бордюр
const COLOR_DASH = 0xc084fc;
const COLOR_GLASS = 0x2e2a6b;
const COLOR_HEADLIGHT = 0xfef08a;
const COLOR_TAILLIGHT = 0xf43f5e;

// Неподвижная камера: сверху-сбоку, видит всю трассу целиком.
const CAMERA = { fov: 40, elevationDeg: 52, distance: 700, lookAtZ: 8 };

// Пропорции трёх моделей (единица мира = 1 пиксель прежнего холста).
// Нос машинки направлен вдоль локальной оси +x, как угол angle = 0 в физике.
const CAR_SHAPES = {
  // Спорткар: низкий, длинный, узкий, со спойлером
  racer: {
    length: 38, width: 17, bodyHeight: 6, cabinLength: 14, cabinWidth: 12, cabinHeight: 5,
    cabinX: -3, wheelRadius: 4.2, wheelWidth: 4, spoiler: true,
  },
  // Дрифтер: короче и шире
  drifter: {
    length: 33, width: 22, bodyHeight: 7.5, cabinLength: 15, cabinWidth: 15, cabinHeight: 6,
    cabinX: -2, wheelRadius: 5, wheelWidth: 5, spoiler: false,
  },
  // Внедорожник: высокий, с большими колёсами
  tank: {
    length: 35, width: 22, bodyHeight: 11, cabinLength: 20, cabinWidth: 17, cabinHeight: 8,
    cabinX: -2, wheelRadius: 7, wheelWidth: 6, spoiler: false,
  },
};

// Визуальный масштаб машинки (физика и границы не меняются)
const CAR_SCALE = 1.25;

const RING_STEPS = 180;

// Лента между двумя эллипсами (в плоскости x-z) на участке углов [t0, t1].
function pushArcStrip(positions, rx0, rz0, rx1, rz1, t0, t1, steps, y) {
  for (let i = 0; i < steps; i++) {
    const a = t0 + ((t1 - t0) * i) / steps;
    const b = t0 + ((t1 - t0) * (i + 1)) / steps;
    const p0 = [rx0 * Math.cos(a), y, rz0 * Math.sin(a)];
    const p1 = [rx1 * Math.cos(a), y, rz1 * Math.sin(a)];
    const p2 = [rx0 * Math.cos(b), y, rz0 * Math.sin(b)];
    const p3 = [rx1 * Math.cos(b), y, rz1 * Math.sin(b)];
    positions.push(...p0, ...p1, ...p2, ...p1, ...p3, ...p2);
  }
}

function geometryFromPositions(positions) {
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();
  return geometry;
}

// Невысокий бордюр: прямоугольное сечение, протянутое вдоль эллипса.
function buildCurbGeometry(rx, rz, curbWidth, curbHeight) {
  const half = curbWidth / 2;
  const inner = [rx - half, rz - half];
  const outer = [rx + half, rz + half];
  const positions = [];
  const point = (e, t, y) => [e[0] * Math.cos(t), y, e[1] * Math.sin(t)];

  for (let i = 0; i < RING_STEPS; i++) {
    const a = (2 * Math.PI * i) / RING_STEPS;
    const b = (2 * Math.PI * (i + 1)) / RING_STEPS;
    const quad = (p0, p1, p2, p3) => positions.push(...p0, ...p1, ...p2, ...p1, ...p3, ...p2);
    // верх, внутренняя и внешняя стенки
    quad(point(inner, a, curbHeight), point(outer, a, curbHeight),
      point(inner, b, curbHeight), point(outer, b, curbHeight));
    quad(point(inner, a, 0), point(inner, a, curbHeight),
      point(inner, b, 0), point(inner, b, curbHeight));
    quad(point(outer, a, curbHeight), point(outer, a, 0),
      point(outer, b, curbHeight), point(outer, b, 0));
  }
  return geometryFromPositions(positions);
}

function buildCheckerTexture(columns, rows) {
  const cell = 32;
  const canvas = document.createElement("canvas");
  canvas.width = columns * cell;
  canvas.height = rows * cell;
  const ctx = canvas.getContext("2d");
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < columns; c++) {
      ctx.fillStyle = (r + c) % 2 === 0 ? "#000000" : "#FFFFFF";
      ctx.fillRect(c * cell, r * cell, cell, cell);
    }
  }
  const texture = new CanvasTexture(canvas);
  texture.magFilter = NearestFilter;
  texture.minFilter = NearestFilter;
  return texture;
}

function buildTrack(track) {
  const group = new Group();
  const half = track.width / 2;

  // Дорога: лента между контурами бордюров (как в прежней 2D-отрисовке)
  const roadPositions = [];
  pushArcStrip(roadPositions, track.rx - half, track.ry - half, track.rx + half,
    track.ry + half, 0, 2 * Math.PI, RING_STEPS, 0);
  const road = new Mesh(
    geometryFromPositions(roadPositions),
    new MeshStandardMaterial({ color: COLOR_ROAD, roughness: 0.9, metalness: 0, side: DoubleSide }),
  );
  road.receiveShadow = true;
  group.add(road);

  // Бордюры: внутренний голубой, внешний фиолетовый
  const curbInner = new Mesh(
    buildCurbGeometry(track.rx - half, track.ry - half, 5, 3),
    new MeshStandardMaterial({
      color: COLOR_CURB_INNER, emissive: COLOR_CURB_INNER, emissiveIntensity: 0.5,
      side: DoubleSide,
    }),
  );
  const curbOuter = new Mesh(
    buildCurbGeometry(track.rx + half, track.ry + half, 5, 3),
    new MeshStandardMaterial({
      color: COLOR_CURB_OUTER, emissive: COLOR_CURB_OUTER, emissiveIntensity: 0.5,
      side: DoubleSide,
    }),
  );
  curbInner.castShadow = true;
  curbOuter.castShadow = true;
  group.add(curbInner, curbOuter);

  // Пунктирная осевая линия
  const dashPositions = [];
  const dashes = 64;
  for (let i = 0; i < dashes; i++) {
    const t0 = (2 * Math.PI * i) / dashes;
    const t1 = t0 + ((2 * Math.PI) / dashes) * 0.45;
    pushArcStrip(dashPositions, track.rx - 1, track.ry - 1, track.rx + 1, track.ry + 1,
      t0, t1, 2, 0.1);
  }
  const dashLine = new Mesh(
    geometryFromPositions(dashPositions),
    new MeshBasicMaterial({ color: COLOR_DASH, side: DoubleSide, transparent: true, opacity: 0.55 }),
  );
  group.add(dashLine);

  // Клетчатая линия старта и финиша: вверху по центру, поперёк дороги
  const rows = Math.round(track.width / 10);
  const finish = new Mesh(
    new PlaneGeometry(20, track.width),
    new MeshBasicMaterial({ map: buildCheckerTexture(2, rows) }),
  );
  finish.rotation.x = -Math.PI / 2;
  finish.position.set(0, 0.2, -track.ry);
  group.add(finish);

  return group;
}

function box(width, height, depth, material) {
  const mesh = new Mesh(new BoxGeometry(width, height, depth), material);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

// Машинка из простых форм: корпус, кабина, четыре колеса, фары.
function buildCar(modelId, colorHex) {
  const shape = CAR_SHAPES[modelId] || CAR_SHAPES.racer;
  const car = new Group();

  const bodyMaterial = new MeshStandardMaterial({
    color: new Color(colorHex), roughness: 0.45, metalness: 0.15,
  });
  const glassMaterial = new MeshStandardMaterial({ color: COLOR_GLASS, roughness: 0.2, metalness: 0.4 });
  const wheelMaterial = new MeshStandardMaterial({ color: 0x15122e, roughness: 0.8 });
  const headlightMaterial = new MeshStandardMaterial({
    color: COLOR_HEADLIGHT, emissive: COLOR_HEADLIGHT, emissiveIntensity: 1.2,
  });
  const taillightMaterial = new MeshStandardMaterial({
    color: COLOR_TAILLIGHT, emissive: COLOR_TAILLIGHT, emissiveIntensity: 0.8,
  });

  const clearance = shape.wheelRadius * 0.7;
  const bodyY = clearance + shape.bodyHeight / 2;

  const body = box(shape.length, shape.bodyHeight, shape.width, bodyMaterial);
  body.position.y = bodyY;
  car.add(body);

  const cabin = box(shape.cabinLength, shape.cabinHeight, shape.cabinWidth, glassMaterial);
  cabin.position.set(shape.cabinX, clearance + shape.bodyHeight + shape.cabinHeight / 2, 0);
  car.add(cabin);

  // Колёса: цилиндры, ось вдоль локальной оси z
  const wheelGeometry = new CylinderGeometry(shape.wheelRadius, shape.wheelRadius, shape.wheelWidth, 18);
  wheelGeometry.rotateX(Math.PI / 2);
  for (const sx of [-1, 1]) {
    for (const sz of [-1, 1]) {
      const wheel = new Mesh(wheelGeometry, wheelMaterial);
      wheel.castShadow = true;
      wheel.position.set(
        sx * shape.length * 0.3,
        shape.wheelRadius,
        sz * (shape.width / 2 + shape.wheelWidth / 2 - 1),
      );
      car.add(wheel);
    }
  }

  // Фары спереди, задние огни сзади
  for (const sz of [-1, 1]) {
    const headlight = box(1.5, 2.2, 3.4, headlightMaterial);
    headlight.position.set(shape.length / 2, bodyY + shape.bodyHeight * 0.1, sz * shape.width * 0.3);
    car.add(headlight);
    const taillight = box(1.2, 1.8, 3, taillightMaterial);
    taillight.position.set(-shape.length / 2, bodyY + shape.bodyHeight * 0.1, sz * shape.width * 0.32);
    car.add(taillight);
  }

  if (shape.spoiler) {
    const spoiler = box(4, 1.2, shape.width + 1, bodyMaterial);
    spoiler.position.set(-shape.length / 2 + 2, clearance + shape.bodyHeight + 3.5, 0);
    car.add(spoiler);
    for (const sz of [-1, 1]) {
      const strut = box(1.2, 3, 1.2, glassMaterial);
      strut.position.set(-shape.length / 2 + 2, clearance + shape.bodyHeight + 1.5, sz * shape.width * 0.3);
      car.add(strut);
    }
  }

  car.userData.topY = clearance + shape.bodyHeight + shape.cabinHeight;
  car.scale.setScalar(CAR_SCALE);
  return car;
}

// Подпись игрока: плоский объект, всегда повёрнутый к камере, поэтому горизонтальный
function buildLabel(text, colorHex) {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 64;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "rgba(13, 10, 31, 0.78)";
  ctx.beginPath();
  ctx.roundRect(6, 8, 116, 48, 12);
  ctx.fill();
  ctx.lineWidth = 4;
  ctx.strokeStyle = colorHex;
  ctx.stroke();
  ctx.font = "bold 34px sans-serif";
  ctx.fillStyle = "#FFFFFF";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 64, 33);

  const sprite = new Sprite(new SpriteMaterial({
    map: new CanvasTexture(canvas), transparent: true, depthTest: false,
  }));
  sprite.scale.set(30, 15, 1);
  sprite.renderOrder = 10;
  return sprite;
}

/**
 * Создаёт 3D-сцену на готовом canvas. Бросает ошибку, если 3D в браузере недоступно.
 *
 * @param canvas  элемент canvas (размеры берутся из него)
 * @param track   параметры трассы trackConfig (cx, cy, rx, ry, width)
 * @param players [{ modelId, colorHex, label }] для каждой машинки
 * @returns { render(states), dispose() }, где states = [{ x, y, angle }] в координатах 2D-холста
 */
export function createRaceScene(canvas, track, players) {
  const renderer = new WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(canvas.width, canvas.height, false);
  renderer.shadowMap.enabled = true;

  const scene = new Scene();
  scene.background = new Color(COLOR_BACKGROUND);

  // Камера: неподвижная, смотрит в центр трассы сверху-сбоку
  const camera = new PerspectiveCamera(CAMERA.fov, canvas.width / canvas.height, 10, 3000);
  const elevation = (CAMERA.elevationDeg * Math.PI) / 180;
  camera.position.set(0, Math.sin(elevation) * CAMERA.distance, Math.cos(elevation) * CAMERA.distance);
  camera.lookAt(0, 0, CAMERA.lookAtZ);

  // Свет: мягкий общий и один направленный с тенями
  scene.add(new AmbientLight(0xb8a8ff, 0.42));
  scene.add(new HemisphereLight(0xc4b5fd, 0x1a1033, 0.45));
  const sun = new DirectionalLight(0xffffff, 1.8);
  sun.position.set(-220, 380, 160);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -420;
  sun.shadow.camera.right = 420;
  sun.shadow.camera.top = 300;
  sun.shadow.camera.bottom = -300;
  sun.shadow.camera.near = 50;
  sun.shadow.camera.far = 1200;
  sun.shadow.bias = -0.0006;
  sun.shadow.normalBias = 0.6;
  scene.add(sun);

  // Земля вокруг трассы
  const ground = new Mesh(
    new PlaneGeometry(2400, 2400),
    new MeshStandardMaterial({ color: COLOR_BACKGROUND, roughness: 1 }),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.5;
  ground.receiveShadow = true;
  scene.add(ground);

  scene.add(buildTrack(track));

  const cars = players.map((player) => {
    const car = buildCar(player.modelId, player.colorHex);
    const label = buildLabel(player.label, player.colorHex);
    label.position.set(0, car.userData.topY + 26, 0);
    car.add(label);
    scene.add(car);
    return car;
  });

  function render(states) {
    states.forEach((state, i) => {
      const car = cars[i];
      if (!car) return;
      // Игровое y (вниз по экрану) становится осью z (к камере); поворот вокруг вертикали = -angle
      car.position.set(state.x - track.cx, 0, state.y - track.cy);
      car.rotation.y = -state.angle;
    });
    renderer.render(scene, camera);
  }

  function dispose() {
    scene.traverse((object) => {
      if (object.geometry) object.geometry.dispose();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach((material) => {
        if (!material) return;
        if (material.map) material.map.dispose();
        material.dispose();
      });
    });
    renderer.dispose();
    renderer.forceContextLoss();
  }

  return { render, dispose };
}
