type FaceProps = {
  emotion: string;
  animation: string;
  speaking: boolean;
  name: string;
  role: string;
  ink: string;
  paper: string;
};

export function ActorCard({ emotion, animation, speaking, name, role, ink, paper }: FaceProps) {
  const eyes = eyeStyle(emotion);
  return (
    <article className="flex flex-col items-center gap-3 rounded-3xl px-4 py-6" style={{ background: paper, color: ink }}>
      <svg viewBox="0 0 160 180" className={`h-40 w-40 ${animation ? `anim-${animation}` : ""}`} aria-hidden="true">
        <circle cx="80" cy="78" r="52" fill={ink} />
        <ellipse cx="58" cy="72" rx="8" ry={eyes.ry} fill={paper} transform={eyes.left} />
        <ellipse cx="102" cy="72" rx="8" ry={eyes.ry} fill={paper} transform={eyes.right} />
        <path d={mouthPath(emotion, speaking)} stroke={paper} strokeWidth="3" fill="none" strokeLinecap="round" />
        {emotion === "EMOTION_FRUSTRATION" && (
          <path d="M48 52 Q58 46 68 54" stroke={paper} strokeWidth="3" fill="none" />
        )}
      </svg>
      <div className="text-center">
        <h2 className="text-xl">{name}</h2>
        <p className="text-sm opacity-80">{role}</p>
      </div>
    </article>
  );
}

function eyeStyle(emotion: string) {
  if (emotion === "EMOTION_DISAPPOINTMENT") {
    return { ry: 4, left: "rotate(-12 58 72)", right: "rotate(12 102 72)" };
  }
  if (emotion === "EMOTION_ENCOURAGEMENT" || emotion === "EMOTION_AMUSEMENT") {
    return { ry: 6, left: "", right: "" };
  }
  return { ry: 8, left: "", right: "" };
}

function mouthPath(emotion: string, speaking: boolean) {
  if (speaking) return "M58 104 Q80 118 102 104";
  if (emotion === "EMOTION_DISAPPOINTMENT" || emotion === "EMOTION_FRUSTRATION") {
    return "M60 112 Q80 100 100 112";
  }
  if (emotion === "EMOTION_ENCOURAGEMENT" || emotion === "EMOTION_AMUSEMENT") {
    return "M58 102 Q80 118 102 102";
  }
  return "M62 108 H98";
}
