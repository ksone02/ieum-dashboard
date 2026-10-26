import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { CircleCheck, LoaderCircle } from 'lucide-react';

/* Aceternity UI Multi Step Loader의 단계 표시 방식을 따름: 에이전트가 실제로 하는 일을 순서대로 보여 줌.
   자료가 오면 남은 단계를 빠르게 끝내고 닫힘. 숫자는 실제 조사 범위임. */
const STEPS = [
  '동네별로 연락·외출이 적은 집단을 찾고 있어요',
  '사업 54개의 신청 조건을 하나씩 확인하고 있어요',
  '조건을 바꾸면 누가 갈 수 있는지 다시 따져 보고 있어요',
  '먼저 살펴볼 동네를 고르고 있어요',
];

export default function ScanLoader({ done, onFinish }: { done: boolean; onFinish: () => void }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    if (step >= STEPS.length) {
      const t = setTimeout(onFinish, 350);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setStep(s => (s < STEPS.length - 1 || done ? s + 1 : s)), done ? 260 : 650);
    return () => clearTimeout(t);
  }, [step, done, onFinish]);
  return (
    <div className="scan" role="status" aria-live="polite">
      <div className="scan-card">
        <p className="scan-title">에이전트가 점검하고 있어요</p>
        <ol>
          {STEPS.map((s, i) => (
            <motion.li
              key={s}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: i <= step ? 1 : 0.35, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              {i < step ? (
                <CircleCheck className="ok" size={18} />
              ) : i === step ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <span className="todo" />
              )}
              {s}
            </motion.li>
          ))}
        </ol>
      </div>
    </div>
  );
}
