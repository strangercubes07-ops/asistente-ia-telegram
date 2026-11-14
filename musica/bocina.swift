// bocina: conecta una bocina Bluetooth ya emparejada y manda el audio de la Mac ahí.
// Uso:
//   bocina lista                 -> bocinas Bluetooth emparejadas y salidas de audio
//   bocina conectar "Nombre"     -> conecta por Bluetooth y la pone como salida
//   bocina salida "Nombre"       -> solo cambia la salida de audio (ej. "Altavoces del MacBook Air")
//   bocina desconectar "Nombre"  -> desconecta la bocina Bluetooth
import Foundation
import IOBluetooth
import CoreAudio

func emparejados() -> [IOBluetoothDevice] {
    (IOBluetoothDevice.pairedDevices() as? [IOBluetoothDevice]) ?? []
}

func buscarBT(_ nombre: String) -> IOBluetoothDevice? {
    let n = nombre.lowercased()
    let ds = emparejados()
    return ds.first { ($0.name ?? "").lowercased() == n } ?? ds.first { ($0.name ?? "").lowercased().contains(n) }
}

func dispositivosSalida() -> [(AudioDeviceID, String)] {
    var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDevices,
        mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size)
    var ids = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &ids)
    var res: [(AudioDeviceID, String)] = []
    for id in ids {
        var sAddr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyStreams,
            mScope: kAudioDevicePropertyScopeOutput, mElement: kAudioObjectPropertyElementMain)
        var sSize: UInt32 = 0
        AudioObjectGetPropertyDataSize(id, &sAddr, 0, nil, &sSize)
        if sSize == 0 { continue }
        var nAddr = AudioObjectPropertyAddress(mSelector: kAudioObjectPropertyName,
            mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
        var nombre: Unmanaged<CFString>?
        var nSize = UInt32(MemoryLayout<Unmanaged<CFString>?>.size)
        if AudioObjectGetPropertyData(id, &nAddr, 0, nil, &nSize, &nombre) == noErr, let n = nombre {
            res.append((id, n.takeRetainedValue() as String))
        }
    }
    return res
}

func ponerSalida(_ nombre: String) -> Bool {
    let n = nombre.lowercased()
    let ds = dispositivosSalida()
    guard let d = ds.first(where: { $0.1.lowercased() == n }) ?? ds.first(where: { $0.1.lowercased().contains(n) }) else { return false }
    var id = d.0
    for sel in [kAudioHardwarePropertyDefaultOutputDevice, kAudioHardwarePropertyDefaultSystemOutputDevice] {
        var addr = AudioObjectPropertyAddress(mSelector: sel,
            mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
        AudioObjectSetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil,
            UInt32(MemoryLayout<AudioDeviceID>.size), &id)
    }
    print("Salida de audio: \(d.1)")
    return true
}

let args = CommandLine.arguments
let cmd = args.count > 1 ? args[1] : "lista"
let nombre = args.count > 2 ? args[2...].joined(separator: " ") : ""

switch cmd {
case "lista":
    print("Bocinas Bluetooth emparejadas:")
    for d in emparejados() { print("- \(d.name ?? "?")\(d.isConnected() ? " (conectada)" : "")") }
    print("Salidas de audio disponibles ahora:")
    for (_, n) in dispositivosSalida() { print("- \(n)") }
case "conectar":
    guard let d = buscarBT(nombre) else { print("No encontré \"\(nombre)\" emparejada. Primero hay que emparejarla en Ajustes > Bluetooth."); exit(1) }
    if !d.isConnected() {
        let r = d.openConnection()
        if r != kIOReturnSuccess { print("No pude conectar \(d.name ?? nombre): ¿está prendida y cerca? (código \(r))"); exit(1) }
    }
    // Esperar a que aparezca como salida de audio
    for _ in 0..<20 {
        if ponerSalida(d.name ?? nombre) { print("Conectada: \(d.name ?? nombre)"); exit(0) }
        Thread.sleep(forTimeInterval: 0.5)
    }
    print("Se conectó \(d.name ?? nombre) pero no apareció como salida de audio."); exit(1)
case "salida":
    if !ponerSalida(nombre) { print("No encontré la salida \"\(nombre)\"."); exit(1) }
case "desconectar":
    guard let d = buscarBT(nombre) else { print("No encontré \"\(nombre)\"."); exit(1) }
    d.closeConnection(); print("Desconectada: \(d.name ?? nombre)")
default:
    print("Uso: bocina lista | conectar NOMBRE | salida NOMBRE | desconectar NOMBRE"); exit(1)
}
