// Embedded architecture of the physical robot: Raspberry Pi over serial to an Arduino Uno (motion) and an STM32 (distance).
// Source: huseyinTozluyurt/Indoor-Autonomous-Robot-for-Delivery (firmware and Pi scripts).
export default function EmbeddedArch() {
  const box = (x, y, w, h, cls, title, sub) => (
    <g className={`arch-node ${cls}`}>
      <rect x={x} y={y} width={w} height={h} rx="10" />
      <text x={x + 14} y={y + 26} className="arch-title">{title}</text>
      {sub.map((s, i) => (
        <text key={i} x={x + 14} y={y + 46 + i * 17} className="arch-sub">{s}</text>
      ))}
    </g>
  )
  return (
    <figure className="diagram">
      <svg viewBox="0 0 960 440" role="img" aria-labelledby="emb-t emb-d">
        <title id="emb-t">Embedded architecture of the physical robot</title>
        <desc id="emb-d">A Raspberry Pi 4 sends motion commands over USB serial to an Arduino Uno, which drives four DC motors through two L298N drivers and reads an MPU6050 IMU over I2C. An STM32F103 triggers four HC-SR04 ultrasonic sensors and streams their distances to the Pi over UART.</desc>
        <defs>
          <marker id="eh" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" className="arch-head" />
          </marker>
        </defs>

        <text x="20" y="24" className="arch-zone">High-level control</text>
        <text x="20" y="190" className="arch-zone">Real-time firmware</text>
        <text x="20" y="352" className="arch-zone">Hardware</text>

        {box(330, 36, 300, 96, 'n-be', 'Raspberry Pi 4 · Python', ['menus and missions in timed chunks', 'yaw supervision · sensor logging (pyserial)'])}
        {box(60, 202, 340, 104, 'n-wb', 'Arduino Uno · C++', ['parses F/B/L/R/S <left> <right> <ms>', 'per-side trim · gyro yaw integration', '5° drift → stop, counter-turn, resume'])}
        {box(560, 202, 340, 104, 'n-wb', 'STM32F103C8T6 · HAL', ['TIM2 as a 1 MHz echo timer', 'fires 4 sensors in turn, 60 ms apart', 'one CSV line every ~300 ms'])}

        {box(20, 364, 190, 64, 'n-gz', 'MPU6050', ['I²C 0x68 · A4 / A5'])}
        {box(230, 364, 210, 64, 'n-gz', '2 × L298N → 4 motors', ['PWM D3 D5 D6 D11'])}
        {box(560, 364, 340, 64, 'n-gz', '4 × HC-SR04', ['TRIG PB0 PB1 PB10 PB11 · ECHO PA0–PA3'])}

        <line x1="400" y1="132" x2="250" y2="200" className="arch-edge" markerEnd="url(#eh)" />
        <text x="120" y="146" className="arch-lbl">USB /dev/ttyUSB0 · 115200</text>
        <text x="120" y="162" className="arch-lbl">F 200 200 3000 ↓   ACK / DONE ↑</text>

        <line x1="720" y1="200" x2="565" y2="134" className="arch-edge" markerEnd="url(#eh)" />
        <text x="680" y="146" className="arch-lbl">UART /dev/ttyS0 · 115200 8N1</text>
        <text x="680" y="162" className="arch-lbl">35,42,28,999,1 ↑</text>

        <line x1="115" y1="306" x2="115" y2="362" className="arch-edge" markerEnd="url(#eh)" />
        <text x="123" y="338" className="arch-lbl">I²C</text>
        <line x1="335" y1="306" x2="335" y2="362" className="arch-edge" markerEnd="url(#eh)" />
        <text x="343" y="338" className="arch-lbl">PWM + DIR</text>
        <line x1="730" y1="306" x2="730" y2="362" className="arch-edge" markerEnd="url(#eh)" />
        <text x="738" y="338" className="arch-lbl">TRIG / ECHO</text>
      </svg>
      <figcaption>Each microcontroller does one time-critical job; the Pi only sends commands and reads results over serial.</figcaption>
    </figure>
  )
}
