import type { MaterialTheme } from '../materials/materials';

// ==========================================
// 1. BEDROOM FURNITURE (Teal Velvet Suite)
// ==========================================

export function BedDouble({
  width = 1.9,
  length = 2.15,
  theme,
}: {
  width?: number;
  length?: number;
  theme: MaterialTheme;
}) {
  const headboardH = 1.05;
  const mattressH = 0.25;
  const frameH = 0.3;
  const nightstandW = 0.45;
  const nightstandD = 0.4;
  const nightstandH = 0.45;

  return (
    <group>
      {/* Accent Woven Rug Under Bed */}
      <mesh position={[0, 0.012, 0.3]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[width + 1.2, length + 0.8]} />
        <meshStandardMaterial {...theme.rugSlateBlue} />
      </mesh>

      {/* Rich Teal/Petrol Velvet Headboard */}
      <mesh position={[0, headboardH / 2, -length / 2 + 0.05]} castShadow receiveShadow>
        <boxGeometry args={[width + 0.15, headboardH, 0.1]} />
        <meshStandardMaterial {...theme.bedHeadboardTeal} />
      </mesh>

      {/* Bed Base Frame (Honey Oak) */}
      <mesh position={[0, frameH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[width, frameH, length]} />
        <meshStandardMaterial {...theme.woodFurniture} />
      </mesh>

      {/* Crisp White Hotel Mattress */}
      <mesh position={[0, frameH + mattressH / 2, 0.05]} castShadow receiveShadow>
        <boxGeometry args={[width - 0.06, mattressH, length - 0.12]} />
        <meshStandardMaterial {...theme.bedLinen} />
      </mesh>

      {/* Duvet / Bedspread */}
      <mesh position={[0, frameH + mattressH + 0.03, 0.22]} castShadow receiveShadow>
        <boxGeometry args={[width - 0.02, 0.06, length * 0.7]} />
        <meshStandardMaterial {...theme.bedDuvet} />
      </mesh>

      {/* Folded Slate-Grey Accent Throw */}
      <mesh position={[0, frameH + mattressH + 0.065, 0.65]} castShadow receiveShadow>
        <boxGeometry args={[width + 0.02, 0.03, 0.55]} />
        <meshStandardMaterial {...theme.bedThrow} />
      </mesh>

      {/* Pillows (Dual Pairs with Angle) */}
      <group position={[0, frameH + mattressH + 0.08, -length / 2 + 0.35]}>
        {/* Left Pillows */}
        <mesh position={[-width / 4, 0, 0]} rotation={[-0.2, 0, 0]} castShadow>
          <boxGeometry args={[width * 0.36, 0.11, 0.42]} />
          <meshStandardMaterial {...theme.bedLinen} />
        </mesh>
        <mesh position={[-width / 4, 0.05, 0.12]} rotation={[-0.3, 0, 0]} castShadow>
          <boxGeometry args={[width * 0.3, 0.09, 0.35]} />
          <meshStandardMaterial {...theme.cushionBlue} />
        </mesh>

        {/* Right Pillows */}
        <mesh position={[width / 4, 0, 0]} rotation={[-0.2, 0, 0]} castShadow>
          <boxGeometry args={[width * 0.36, 0.11, 0.42]} />
          <meshStandardMaterial {...theme.bedLinen} />
        </mesh>
        <mesh position={[width / 4, 0.05, 0.12]} rotation={[-0.3, 0, 0]} castShadow>
          <boxGeometry args={[width * 0.3, 0.09, 0.35]} />
          <meshStandardMaterial {...theme.cushionBlue} />
        </mesh>
      </group>

      {/* Left Nightstand & Warm Bedside Lamp */}
      <group position={[-width / 2 - nightstandW / 2 - 0.08, 0, -length / 2 + nightstandD / 2 + 0.05]}>
        <mesh position={[0, nightstandH / 2, 0]} castShadow receiveShadow>
          <boxGeometry args={[nightstandW, nightstandH, nightstandD]} />
          <meshStandardMaterial {...theme.woodFurniture} />
        </mesh>
        {/* Lamp Base & Brass Stem */}
        <mesh position={[0, nightstandH + 0.07, 0]} castShadow>
          <cylinderGeometry args={[0.04, 0.06, 0.14, 12]} />
          <meshStandardMaterial {...theme.brassGold} />
        </mesh>
        {/* Luminous Warm Lamp Shade */}
        <mesh position={[0, nightstandH + 0.2, 0]} castShadow>
          <cylinderGeometry args={[0.09, 0.12, 0.15, 16]} />
          <meshStandardMaterial {...theme.lampGlow} />
        </mesh>
        <pointLight position={[0, nightstandH + 0.2, 0]} intensity={0.4} distance={3.5} color="#FFDF9E" />
      </group>

      {/* Right Nightstand & Warm Bedside Lamp */}
      <group position={[width / 2 + nightstandW / 2 + 0.08, 0, -length / 2 + nightstandD / 2 + 0.05]}>
        <mesh position={[0, nightstandH / 2, 0]} castShadow receiveShadow>
          <boxGeometry args={[nightstandW, nightstandH, nightstandD]} />
          <meshStandardMaterial {...theme.woodFurniture} />
        </mesh>
        {/* Lamp Base & Brass Stem */}
        <mesh position={[0, nightstandH + 0.07, 0]} castShadow>
          <cylinderGeometry args={[0.04, 0.06, 0.14, 12]} />
          <meshStandardMaterial {...theme.brassGold} />
        </mesh>
        {/* Luminous Warm Lamp Shade */}
        <mesh position={[0, nightstandH + 0.2, 0]} castShadow>
          <cylinderGeometry args={[0.09, 0.12, 0.15, 16]} />
          <meshStandardMaterial {...theme.lampGlow} />
        </mesh>
        <pointLight position={[0, nightstandH + 0.2, 0]} intensity={0.4} distance={3.5} color="#FFDF9E" />
      </group>
    </group>
  );
}

export function Wardrobe({
  width = 1.8,
  height = 1.8,
  depth = 0.6,
  theme,
}: {
  width?: number;
  height?: number;
  depth?: number;
  theme: MaterialTheme;
}) {
  return (
    <group>
      {/* Main Wardrobe Cabinet */}
      <mesh position={[0, height / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial {...theme.woodFurniture} />
      </mesh>

      {/* Door Panels Divider Line */}
      <mesh position={[0, height / 2, depth / 2 + 0.005]}>
        <boxGeometry args={[0.015, height * 0.95, 0.01]} />
        <meshStandardMaterial {...theme.darkWood} />
      </mesh>

      {/* Satin Brass Modern Bar Handles */}
      <mesh position={[-0.04, height * 0.5, depth / 2 + 0.02]} castShadow>
        <boxGeometry args={[0.018, 0.25, 0.02]} />
        <meshStandardMaterial {...theme.brassGold} />
      </mesh>
      <mesh position={[0.04, height * 0.5, depth / 2 + 0.02]} castShadow>
        <boxGeometry args={[0.018, 0.25, 0.02]} />
        <meshStandardMaterial {...theme.brassGold} />
      </mesh>
    </group>
  );
}

// ==========================================
// 2. LIVING ROOM FURNITURE (Dual Sofas & Marble/Brass Tables)
// ==========================================

export function LivingSet({
  theme,
}: {
  theme: MaterialTheme;
}) {
  const sofaW = 2.3;
  const sofaD = 0.88;
  const sofaH = 0.72;
  const seatH = 0.4;

  return (
    <group>
      {/* 1. Large Slate Denim Blue Area Rug */}
      <mesh position={[0, 0.012, 0.55]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[3.2, 2.5]} />
        <meshStandardMaterial {...theme.rugSlateBlue} />
      </mesh>

      {/* 2. Layered Circular Neutral Accent Rug */}
      <mesh position={[-0.4, 0.015, 0.7]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <circleGeometry args={[0.7, 32]} />
        <meshStandardMaterial {...theme.rugNeutral} />
      </mesh>

      {/* 3. Primary 3-Seater Sofa (Facing Room) */}
      <group position={[0, 0, 0]}>
        {/* Plinth Base */}
        <mesh position={[0, 0.05, 0]} castShadow receiveShadow>
          <boxGeometry args={[sofaW - 0.05, 0.1, sofaD - 0.05]} />
          <meshStandardMaterial {...theme.woodFurniture} />
        </mesh>

        {/* Seat Cushion */}
        <mesh position={[0, seatH / 2 + 0.08, 0.02]} castShadow receiveShadow>
          <boxGeometry args={[sofaW, seatH, sofaD]} />
          <meshStandardMaterial {...theme.sofaFabric} />
        </mesh>

        {/* Low Backrest */}
        <mesh position={[0, sofaH / 2 + 0.1, -sofaD / 2 + 0.12]} castShadow>
          <boxGeometry args={[sofaW, sofaH - 0.2, 0.24]} />
          <meshStandardMaterial {...theme.sofaFabric} />
        </mesh>

        {/* Left Armrest */}
        <mesh position={[-sofaW / 2 + 0.11, 0.52 / 2 + 0.05, 0]} castShadow>
          <boxGeometry args={[0.22, 0.52, sofaD]} />
          <meshStandardMaterial {...theme.sofaFabric} />
        </mesh>

        {/* Right Armrest */}
        <mesh position={[sofaW / 2 - 0.11, 0.52 / 2 + 0.05, 0]} castShadow>
          <boxGeometry args={[0.22, 0.52, sofaD]} />
          <meshStandardMaterial {...theme.sofaFabric} />
        </mesh>

        {/* Accent Pillows (Slate Blue & Cream Textured) */}
        <mesh position={[-0.65, seatH + 0.14, -0.15]} rotation={[0.15, 0.25, 0]} castShadow>
          <boxGeometry args={[0.38, 0.38, 0.12]} />
          <meshStandardMaterial {...theme.cushionBlue} />
        </mesh>
        <mesh position={[-0.35, seatH + 0.12, -0.18]} rotation={[0.12, 0.1, 0]} castShadow>
          <boxGeometry args={[0.34, 0.34, 0.1]} />
          <meshStandardMaterial {...theme.cushionFabric} />
        </mesh>
        <mesh position={[0.65, seatH + 0.14, -0.15]} rotation={[0.15, -0.25, 0]} castShadow>
          <boxGeometry args={[0.38, 0.38, 0.12]} />
          <meshStandardMaterial {...theme.cushionBlue} />
        </mesh>
      </group>

      {/* 4. Secondary Loveseat / 2-Seater (Perpendicular L-Arrangement) */}
      <group position={[-1.7, 0, 0.85]} rotation={[0, Math.PI / 2, 0]}>
        <mesh position={[0, 0.05, 0]} castShadow receiveShadow>
          <boxGeometry args={[1.5, 0.1, sofaD - 0.05]} />
          <meshStandardMaterial {...theme.woodFurniture} />
        </mesh>
        <mesh position={[0, seatH / 2 + 0.08, 0.02]} castShadow receiveShadow>
          <boxGeometry args={[1.55, seatH, sofaD]} />
          <meshStandardMaterial {...theme.sofaFabric} />
        </mesh>
        <mesh position={[0, sofaH / 2 + 0.1, -sofaD / 2 + 0.12]} castShadow>
          <boxGeometry args={[1.55, sofaH - 0.2, 0.24]} />
          <meshStandardMaterial {...theme.sofaFabric} />
        </mesh>
        {/* Armrest */}
        <mesh position={[1.55 / 2 - 0.1, 0.52 / 2 + 0.05, 0]} castShadow>
          <boxGeometry args={[0.2, 0.52, sofaD]} />
          <meshStandardMaterial {...theme.sofaFabric} />
        </mesh>
        <mesh position={[0, seatH + 0.14, -0.15]} rotation={[0.15, 0, 0]} castShadow>
          <boxGeometry args={[0.36, 0.36, 0.12]} />
          <meshStandardMaterial {...theme.cushionBlue} />
        </mesh>
      </group>

      {/* 5. Elegant Rectangular Carrara Marble & Brass Coffee Table */}
      <group position={[0.2, 0, 0.85]}>
        {/* Marble Top */}
        <mesh position={[0, 0.36, 0]} castShadow receiveShadow>
          <boxGeometry args={[1.15, 0.035, 0.6]} />
          <meshStandardMaterial {...theme.marbleTable} />
        </mesh>
        {/* Warm Satin Brass Frame & Thin Legs */}
        {[-0.52, 0.52].map((x) =>
          [-0.26, 0.26].map((z) => (
            <mesh key={`cleg_${x}_${z}`} position={[x, 0.17, z]} castShadow>
              <cylinderGeometry args={[0.012, 0.012, 0.34, 8]} />
              <meshStandardMaterial {...theme.brassGold} />
            </mesh>
          ))
        )}
        {/* Perimeter Brass Base Runner */}
        <mesh position={[0, 0.02, 0]} castShadow>
          <boxGeometry args={[1.05, 0.015, 0.52]} />
          <meshStandardMaterial {...theme.brassGold} />
        </mesh>
      </group>

      {/* 6. Round Auxiliary Coffee Table / Pouf */}
      <group position={[-0.55, 0, 1.25]}>
        <mesh position={[0, 0.3, 0]} castShadow receiveShadow>
          <cylinderGeometry args={[0.26, 0.26, 0.03, 24]} />
          <meshStandardMaterial {...theme.marbleTable} />
        </mesh>
        <mesh position={[0, 0.15, 0]} castShadow>
          <cylinderGeometry args={[0.016, 0.016, 0.3, 8]} />
          <meshStandardMaterial {...theme.brassGold} />
        </mesh>
        <mesh position={[0, 0.015, 0]}>
          <cylinderGeometry args={[0.18, 0.18, 0.03, 16]} />
          <meshStandardMaterial {...theme.brassGold} />
        </mesh>
      </group>

      {/* 7. Low Honey Oak TV Credenza & Ultra-Slim TV */}
      <group position={[0, 0, 2.15]}>
        {/* Honey Oak Body */}
        <mesh position={[0, 0.22, 0]} castShadow receiveShadow>
          <boxGeometry args={[1.9, 0.44, 0.38]} />
          <meshStandardMaterial {...theme.woodFurniture} />
        </mesh>
        {/* Modern Shelf Cutouts */}
        <mesh position={[0, 0.22, 0.19]}>
          <boxGeometry args={[1.86, 0.02, 0.01]} />
          <meshStandardMaterial {...theme.darkWood} />
        </mesh>

        {/* Framed Wall Art / Television */}
        <group position={[0, 0.72, 0]}>
          <mesh castShadow>
            <boxGeometry args={[1.35, 0.75, 0.035]} />
            <meshStandardMaterial {...theme.tvScreen} />
          </mesh>
          <mesh position={[0, -0.4, 0]}>
            <boxGeometry args={[0.42, 0.02, 0.18]} />
            <meshStandardMaterial {...theme.brassGold} />
          </mesh>
        </group>
      </group>

      {/* 8. Modern Brass Floor Lamp with Warm Ambient Glow */}
      <group position={[1.45, 0, -0.25]}>
        {/* Heavy Brass Base Disc */}
        <mesh position={[0, 0.02, 0]} castShadow>
          <cylinderGeometry args={[0.15, 0.15, 0.03, 20]} />
          <meshStandardMaterial {...theme.brassGold} />
        </mesh>
        {/* Slender Brass Stem */}
        <mesh position={[0, 0.75, 0]} castShadow>
          <cylinderGeometry args={[0.012, 0.012, 1.45, 8]} />
          <meshStandardMaterial {...theme.brassGold} />
        </mesh>
        {/* Cream Cylindrical Shade */}
        <mesh position={[0, 1.42, 0]} castShadow>
          <cylinderGeometry args={[0.16, 0.16, 0.32, 24]} />
          <meshStandardMaterial {...theme.lampGlow} />
        </mesh>
        {/* Warm Golden Interior Lamp Glow */}
        <pointLight position={[0, 1.4, 0]} intensity={0.6} distance={4.5} color="#FFDF9E" />
      </group>

      {/* 9. Potted Fiddle Leaf Fig in White Ceramic Pot */}
      <group position={[1.45, 0, 1.4]}>
        <mesh position={[0, 0.25, 0]} castShadow>
          <cylinderGeometry args={[0.2, 0.16, 0.5, 20]} />
          <meshStandardMaterial {...theme.plantPotWhite} />
        </mesh>
        {/* Foliage Canopy */}
        <mesh position={[0, 0.75, 0]} castShadow>
          <sphereGeometry args={[0.32, 16, 16]} />
          <meshStandardMaterial {...theme.indoorPlant} />
        </mesh>
      </group>
    </group>
  );
}

// ==========================================
// 3. DINING ROOM FURNITURE (Honey Oak & Scandinavian Chairs)
// ==========================================

export function DiningSet({
  theme,
}: {
  theme: MaterialTheme;
}) {
  const tableW = 1.7;
  const tableD = 0.9;
  const tableH = 0.75;
  const chairW = 0.44;
  const chairD = 0.44;
  const seatH = 0.45;

  return (
    <group>
      {/* Slate Denim Blue Area Rug Under Dining Set */}
      <mesh position={[0, 0.012, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[2.7, 2.0]} />
        <meshStandardMaterial {...theme.rugSlateBlue} />
      </mesh>

      {/* Solid Honey Oak Dining Table Top */}
      <mesh position={[0, tableH, 0]} castShadow receiveShadow>
        <boxGeometry args={[tableW, 0.045, tableD]} />
        <meshStandardMaterial {...theme.woodFurniture} />
      </mesh>

      {/* Tapered Wood Table Legs */}
      {[-tableW / 2 + 0.12, tableW / 2 - 0.12].map((x) =>
        [-tableD / 2 + 0.1, tableD / 2 - 0.1].map((z) => (
          <mesh key={`dleg_${x}_${z}`} position={[x, tableH / 2 - 0.02, z]} castShadow>
            <cylinderGeometry args={[0.028, 0.018, tableH - 0.04, 12]} />
            <meshStandardMaterial {...theme.woodFurniture} />
          </mesh>
        ))
      )}

      {/* Table Centerpiece Decorative Ceramic Bowl */}
      <mesh position={[0, tableH + 0.04, 0]} castShadow>
        <cylinderGeometry args={[0.1, 0.06, 0.06, 16]} />
        <meshStandardMaterial {...theme.plantPotWhite} />
      </mesh>

      {/* 6 Scandinavian Tub Chairs with Cream Upholstered Seats */}
      {/* Front 3 Chairs */}
      {[-0.5, 0, 0.5].map((x, i) => (
        <group key={`front_chair_${i}`} position={[x, 0, tableD / 2 + 0.28]} rotation={[0, Math.PI, 0]}>
          {/* Cream Upholstered Curved Seat */}
          <mesh position={[0, seatH, 0]} castShadow>
            <boxGeometry args={[chairW, 0.05, chairD]} />
            <meshStandardMaterial {...theme.chairFabric} />
          </mesh>
          {/* Curved Backrest */}
          <mesh position={[0, seatH + 0.2, -chairD / 2 + 0.02]} castShadow>
            <boxGeometry args={[chairW, 0.36, 0.04]} />
            <meshStandardMaterial {...theme.chairFabric} />
          </mesh>
          {/* Natural Wood Splayed Legs */}
          {[-0.16, 0.16].map((cx) =>
            [-0.16, 0.16].map((cz) => (
              <mesh key={`cleg_${cx}_${cz}`} position={[cx, seatH / 2, cz]}>
                <cylinderGeometry args={[0.016, 0.012, seatH, 8]} />
                <meshStandardMaterial {...theme.woodFurniture} />
              </mesh>
            ))
          )}
        </group>
      ))}

      {/* Back 3 Chairs */}
      {[-0.5, 0, 0.5].map((x, i) => (
        <group key={`back_chair_${i}`} position={[x, 0, -tableD / 2 - 0.28]}>
          <mesh position={[0, seatH, 0]} castShadow>
            <boxGeometry args={[chairW, 0.05, chairD]} />
            <meshStandardMaterial {...theme.chairFabric} />
          </mesh>
          <mesh position={[0, seatH + 0.2, -chairD / 2 + 0.02]} castShadow>
            <boxGeometry args={[chairW, 0.36, 0.04]} />
            <meshStandardMaterial {...theme.chairFabric} />
          </mesh>
          {[-0.16, 0.16].map((cx) =>
            [-0.16, 0.16].map((cz) => (
              <mesh key={`cleg2_${cx}_${cz}`} position={[cx, seatH / 2, cz]}>
                <cylinderGeometry args={[0.016, 0.012, seatH, 8]} />
                <meshStandardMaterial {...theme.woodFurniture} />
              </mesh>
            ))
          )}
        </group>
      ))}

      {/* Side Accent Potted Plant */}
      <group position={[tableW / 2 + 0.5, 0, 0.3]}>
        <mesh position={[0, 0.2, 0]} castShadow>
          <cylinderGeometry args={[0.18, 0.14, 0.4, 16]} />
          <meshStandardMaterial {...theme.plantPotWhite} />
        </mesh>
        <mesh position={[0, 0.55, 0]} castShadow>
          <sphereGeometry args={[0.26, 12, 12]} />
          <meshStandardMaterial {...theme.indoorPlant} />
        </mesh>
      </group>
    </group>
  );
}

// ==========================================
// 4. KITCHEN FURNITURE & APPLIANCES
// ==========================================

export function KitchenSet({
  length = 3.0,
  theme,
}: {
  length?: number;
  theme: MaterialTheme;
}) {
  const counterDepth = 0.65;
  const counterH = 0.88;

  return (
    <group>
      {/* Base Cabinets (Slate-Grey / Sage) */}
      <mesh position={[0, counterH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[length, counterH, counterDepth]} />
        <meshStandardMaterial {...theme.cabinetry} />
      </mesh>

      {/* Pure White Quartz Countertop */}
      <mesh position={[0, counterH + 0.02, 0]} castShadow receiveShadow>
        <boxGeometry args={[length + 0.02, 0.04, counterDepth + 0.03]} />
        <meshStandardMaterial {...theme.countertop} />
      </mesh>

      {/* Stainless Steel Undermount Sink */}
      <group position={[-length / 3, counterH + 0.02, 0]}>
        <mesh>
          <boxGeometry args={[0.65, 0.01, 0.42]} />
          <meshStandardMaterial color="#2B2D30" roughness={0.3} metalness={0.8} />
        </mesh>
        <mesh position={[0, -0.08, 0]}>
          <boxGeometry args={[0.55, 0.15, 0.35]} />
          <meshStandardMaterial color="#888888" roughness={0.2} metalness={0.9} />
        </mesh>
        {/* Gooseneck Chrome Faucet */}
        <group position={[0, 0.02, -0.16]}>
          <mesh position={[0, 0.14, 0]} castShadow>
            <cylinderGeometry args={[0.014, 0.014, 0.28, 12]} />
            <meshStandardMaterial {...theme.chromeFixture} />
          </mesh>
          <mesh position={[0, 0.26, 0.06]} rotation={[Math.PI / 4, 0, 0]}>
            <cylinderGeometry args={[0.013, 0.013, 0.12, 12]} />
            <meshStandardMaterial {...theme.chromeFixture} />
          </mesh>
        </group>
      </group>

      {/* Cooktop & Modern Oven */}
      <group position={[length / 4, counterH + 0.045, 0]}>
        <mesh castShadow>
          <boxGeometry args={[0.65, 0.01, 0.5]} />
          <meshStandardMaterial color="#0A0B0D" roughness={0.15} metalness={0.9} />
        </mesh>
      </group>

      {/* Refrigerator Tower Unit */}
      <group position={[length / 2 + 0.42, 0.9, 0]}>
        <mesh castShadow receiveShadow>
          <boxGeometry args={[0.75, 1.8, counterDepth + 0.05]} />
          <meshStandardMaterial color="#E2E4E8" roughness={0.25} metalness={0.7} />
        </mesh>
        <mesh position={[0.3, 0.2, counterDepth / 2 + 0.04]} castShadow>
          <cylinderGeometry args={[0.012, 0.012, 0.6, 8]} />
          <meshStandardMaterial {...theme.chromeFixture} />
        </mesh>
      </group>
    </group>
  );
}

// ==========================================
// 5. BATHROOM SUITE
// ==========================================

export function BathroomSuite({
  theme,
}: {
  theme: MaterialTheme;
}) {
  return (
    <group>
      {/* Modern Ceramic Toilet */}
      <group position={[-0.65, 0, 0]}>
        <mesh position={[0, 0.5, -0.22]} castShadow receiveShadow>
          <boxGeometry args={[0.38, 0.5, 0.18]} />
          <meshStandardMaterial {...theme.sanitaryCeramic} />
        </mesh>
        <mesh position={[0, 0.22, 0.08]} castShadow receiveShadow>
          <boxGeometry args={[0.36, 0.42, 0.48]} />
          <meshStandardMaterial {...theme.sanitaryCeramic} />
        </mesh>
      </group>

      {/* Floating Honey Oak Vanity & Round Mirror */}
      <group position={[0.55, 0, 0]}>
        <mesh position={[0, 0.45, 0]} castShadow receiveShadow>
          <boxGeometry args={[0.78, 0.5, 0.5]} />
          <meshStandardMaterial {...theme.woodFurniture} />
        </mesh>
        <mesh position={[0, 0.72, 0]} castShadow>
          <boxGeometry args={[0.8, 0.05, 0.52]} />
          <meshStandardMaterial {...theme.countertop} />
        </mesh>
        {/* Round Brass Framed Mirror */}
        <group position={[0, 1.45, -0.22]}>
          <mesh castShadow>
            <cylinderGeometry args={[0.32, 0.32, 0.02, 32]} />
            <meshStandardMaterial {...theme.brassGold} />
          </mesh>
          <mesh position={[0, 0, 0.015]} rotation={[-Math.PI / 2, 0, 0]}>
            <circleGeometry args={[0.3, 32]} />
            <meshStandardMaterial color="#E8F4F8" roughness={0.1} metalness={0.9} />
          </mesh>
        </group>
      </group>

      {/* Glass Shower Screen */}
      <group position={[0, 0, 0.95]}>
        <mesh position={[0, 0.03, 0]}>
          <boxGeometry args={[1.4, 0.06, 0.08]} />
          <meshStandardMaterial color="#444444" roughness={0.5} />
        </mesh>
        <mesh position={[0, 0.95, 0]}>
          <boxGeometry args={[1.35, 1.85, 0.015]} />
          <meshStandardMaterial {...theme.railingGlass} />
        </mesh>
      </group>
    </group>
  );
}

// ==========================================
// 6. BALCONY BISTRO SEATING
// ==========================================

export function BalconySet({
  theme,
}: {
  theme: MaterialTheme;
}) {
  return (
    <group>
      {/* Round Bistro Table */}
      <group position={[0, 0, 0]}>
        <mesh position={[0, 0.72, 0]} castShadow>
          <cylinderGeometry args={[0.35, 0.35, 0.03, 24]} />
          <meshStandardMaterial {...theme.woodFurniture} />
        </mesh>
        <mesh position={[0, 0.36, 0]} castShadow>
          <cylinderGeometry args={[0.025, 0.025, 0.7, 12]} />
          <meshStandardMaterial {...theme.doorFrame} />
        </mesh>
      </group>

      {/* 2 Outdoor Chairs */}
      {[-0.55, 0.55].map((x, i) => (
        <group key={`chair_${i}`} position={[x, 0, 0]} rotation={[0, i === 0 ? Math.PI / 2 : -Math.PI / 2, 0]}>
          <mesh position={[0, 0.44, 0]} castShadow>
            <cylinderGeometry args={[0.2, 0.2, 0.03, 16]} />
            <meshStandardMaterial {...theme.woodFurniture} />
          </mesh>
          <mesh position={[0, 0.65, -0.16]} castShadow>
            <boxGeometry args={[0.36, 0.35, 0.03]} />
            <meshStandardMaterial {...theme.doorFrame} />
          </mesh>
        </group>
      ))}
    </group>
  );
}

// ==========================================
// 7. LAWN & LANDSCAPE GARDEN SET
// ==========================================

export function LawnGardenSet({
  theme,
}: {
  theme: MaterialTheme;
}) {
  return (
    <group>
      {/* 1. Stone Pathway Stepping Stones */}
      {[-0.8, -0.2, 0.4, 1.0].map((z, idx) => (
        <mesh key={`step_${idx}`} position={[0, 0.025, z]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <circleGeometry args={[0.24, 16]} />
          <meshStandardMaterial {...theme.balconyFloor} />
        </mesh>
      ))}

      {/* 2. Potted Garden Shrubs */}
      {[-0.9, 0.9].map((x, idx) => (
        <group key={`garden_plant_${idx}`} position={[x, 0, -0.5]}>
          <mesh position={[0, 0.22, 0]} castShadow>
            <cylinderGeometry args={[0.22, 0.16, 0.44, 16]} />
            <meshStandardMaterial {...theme.plantPotWhite} />
          </mesh>
          <mesh position={[0, 0.58, 0]} castShadow>
            <sphereGeometry args={[0.32, 16, 16]} />
            <meshStandardMaterial {...theme.indoorPlant} />
          </mesh>
        </group>
      ))}

      {/* 3. Outdoor Teak Garden Bench */}
      <group position={[0.7, 0, 0.5]} rotation={[0, -Math.PI / 3, 0]}>
        {/* Bench seat */}
        <mesh position={[0, 0.42, 0]} castShadow>
          <boxGeometry args={[1.2, 0.05, 0.45]} />
          <meshStandardMaterial {...theme.woodFurniture} />
        </mesh>
        {/* Bench back */}
        <mesh position={[0, 0.72, -0.2]} castShadow>
          <boxGeometry args={[1.2, 0.45, 0.04]} />
          <meshStandardMaterial {...theme.woodFurniture} />
        </mesh>
        {/* Legs */}
        {[-0.52, 0.52].map((lx, i) => (
          <mesh key={`leg_${i}`} position={[lx, 0.21, 0]} castShadow>
            <boxGeometry args={[0.06, 0.42, 0.38]} />
            <meshStandardMaterial {...theme.doorFrame} />
          </mesh>
        ))}
      </group>
    </group>
  );
}

// ==========================================
// 8. ARCHITECTURAL STAIRCASE SET
// ==========================================

export function StaircaseSet({
  theme,
  stepsCount = 9,
  width = 1.35,
}: {
  theme: MaterialTheme;
  stepsCount?: number;
  width?: number;
}) {
  const riserH = 0.16;
  const treadD = 0.28;

  return (
    <group position={[0, 0, 0]}>
      {/* Treads and Risers */}
      {Array.from({ length: stepsCount }).map((_, i) => {
        const stepY = i * riserH;
        const stepZ = (i - stepsCount / 2) * treadD;
        return (
          <group key={`step_${i}`}>
            {/* Step Riser Block */}
            <mesh position={[0, stepY + riserH / 2, stepZ]} castShadow receiveShadow>
              <boxGeometry args={[width, riserH, treadD]} />
              <meshStandardMaterial {...theme.woodFurniture} />
            </mesh>
            {/* Bullnose Tread Lip */}
            <mesh position={[0, stepY + riserH - 0.015, stepZ + treadD / 2 - 0.01]} castShadow>
              <boxGeometry args={[width + 0.02, 0.03, 0.04]} />
              <meshStandardMaterial {...theme.woodFurniture} />
            </mesh>
          </group>
        );
      })}

      {/* Modern Black Steel Balustrade & Handrail */}
      <mesh
        position={[width / 2 - 0.04, (stepsCount * riserH) / 2 + 0.45, 0]}
        rotation={[Math.atan2(stepsCount * riserH, stepsCount * treadD), 0, 0]}
        castShadow
      >
        <cylinderGeometry args={[0.025, 0.025, Math.hypot(stepsCount * riserH, stepsCount * treadD) + 0.4, 12]} />
        <meshStandardMaterial {...theme.railingMetal} />
      </mesh>

      {/* Upright Support Balusters */}
      {[-1, 0, 1].map((posMultiplier) => {
        const idx = Math.floor(stepsCount / 2) + posMultiplier * 3;
        const bZ = (idx - stepsCount / 2) * treadD;
        const bY = idx * riserH;
        return (
          <mesh key={`baluster_${posMultiplier}`} position={[width / 2 - 0.04, bY + 0.4, bZ]} castShadow>
            <cylinderGeometry args={[0.015, 0.015, 0.8, 8]} />
            <meshStandardMaterial {...theme.railingMetal} />
          </mesh>
        );
      })}
    </group>
  );
}

// ==========================================
// 9. LAUNDRY & UTILITY WASH SET
// ==========================================

export function UtilitySet({
  theme,
}: {
  theme: MaterialTheme;
}) {
  return (
    <group position={[0, 0, 0]}>
      {/* Front-load Modern Washing Machine */}
      <group position={[-0.45, 0, 0]}>
        {/* Machine Body */}
        <mesh position={[0, 0.44, 0]} castShadow receiveShadow>
          <boxGeometry args={[0.6, 0.85, 0.6]} />
          <meshStandardMaterial color="#E8ECEF" roughness={0.25} metalness={0.15} />
        </mesh>
        {/* Circular Front Porthole Door */}
        <mesh position={[0, 0.42, 0.31]} rotation={[Math.PI / 2, 0, 0]} castShadow>
          <cylinderGeometry args={[0.22, 0.22, 0.04, 24]} />
          <meshStandardMaterial color="#2B303A" roughness={0.1} metalness={0.7} />
        </mesh>
        <mesh position={[0, 0.42, 0.33]} rotation={[Math.PI / 2, 0, 0]}>
          <circleGeometry args={[0.16, 24]} />
          <meshStandardMaterial color="#4A607A" transparent opacity={0.65} roughness={0.1} />
        </mesh>
        {/* Control Dial & Digital Display */}
        <mesh position={[0.18, 0.78, 0.31]} castShadow>
          <cylinderGeometry args={[0.03, 0.03, 0.02, 16]} />
          <meshStandardMaterial color="#1E2024" roughness={0.3} metalness={0.8} />
        </mesh>
      </group>

      {/* Stainless Steel Utility Sink Basin */}
      <group position={[0.35, 0, 0]}>
        <mesh position={[0, 0.42, 0]} castShadow receiveShadow>
          <boxGeometry args={[0.55, 0.84, 0.55]} />
          <meshStandardMaterial {...theme.cabinetry} />
        </mesh>
        {/* Sink Bowl */}
        <mesh position={[0, 0.845, 0]} receiveShadow>
          <boxGeometry args={[0.45, 0.02, 0.45]} />
          <meshStandardMaterial {...theme.chromeFixture} />
        </mesh>
        {/* Chrome Gooseneck Faucet */}
        <mesh position={[0, 0.98, -0.16]} castShadow>
          <cylinderGeometry args={[0.015, 0.015, 0.24, 12]} />
          <meshStandardMaterial {...theme.chromeFixture} />
        </mesh>
      </group>

      {/* Wall Shelf with Laundry Detergents & Folded Towels */}
      <group position={[0, 1.45, -0.22]}>
        <mesh position={[0, 0, 0]} castShadow>
          <boxGeometry args={[1.2, 0.03, 0.25]} />
          <meshStandardMaterial {...theme.woodFurniture} />
        </mesh>
        {/* Folded Clean Linen */}
        <mesh position={[-0.3, 0.08, 0]} castShadow>
          <boxGeometry args={[0.35, 0.12, 0.2]} />
          <meshStandardMaterial color="#F5F5F7" roughness={0.9} />
        </mesh>
        {/* Detergent Bottles */}
        <mesh position={[0.25, 0.12, 0]} castShadow>
          <cylinderGeometry args={[0.05, 0.06, 0.2, 16]} />
          <meshStandardMaterial color="#3B82F6" roughness={0.3} />
        </mesh>
      </group>
    </group>
  );
}
