export const PCM_SAMPLE_RATE = 22050;

export function pcmToObjectUrl(pcm: Uint8Array): string {
  const header = 44;
  const buffer = new ArrayBuffer(header + pcm.length);
  const view = new DataView(buffer);
  const write = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + pcm.length, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, PCM_SAMPLE_RATE, true);
  view.setUint32(28, PCM_SAMPLE_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, pcm.length, true);
  new Uint8Array(buffer, header).set(pcm);
  return URL.createObjectURL(new Blob([buffer], { type: "audio/wav" }));
}

export function playPcm(pcm: Uint8Array, attach?: (audio: HTMLAudioElement) => void): Promise<void> {
  if (pcm.length === 0) return Promise.resolve();
  const url = pcmToObjectUrl(pcm);
  const audio = new Audio(url);
  if (attach) attach(audio);
  return new Promise((resolve) => {
    const finish = () => {
      URL.revokeObjectURL(url);
      resolve();
    };
    audio.onended = finish;
    audio.onerror = finish;
    audio.onpause = finish;
    void audio.play().catch(finish);
  });
}
