export type HoldRecording = {
  stop: () => Promise<Blob>;
};

export async function startRecording(): Promise<HoldRecording> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const chunks: Blob[] = [];
  let recorder: MediaRecorder;
  try {
    recorder = new MediaRecorder(stream);
  } catch (error) {
    stream.getTracks().forEach((track) => track.stop());
    throw error;
  }
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };
  recorder.start();
  let stopped = false;

  return {
    stop() {
      if (stopped) {
        return Promise.resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
      }
      stopped = true;
      const finish = () => {
        stream.getTracks().forEach((track) => track.stop());
        return new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      };
      if (recorder.state === "inactive") return Promise.resolve(finish());
      return new Promise((resolve) => {
        recorder.onstop = () => resolve(finish());
        recorder.stop();
      });
    },
  };
}
