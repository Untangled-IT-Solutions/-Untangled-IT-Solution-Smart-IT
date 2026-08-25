// src/components/LoadingAnimation.tsx
import { useEffect, useState } from 'react';
import { useTheme } from '../context/ThemeContext';

interface LoadingAnimationProps {
  onComplete: () => void;
}

export default function LoadingAnimation({ onComplete }: LoadingAnimationProps) {
  const { theme } = useTheme();
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    // Fast spin for 15 seconds
    const startTime = Date.now();
    const duration = 15000; // 15 seconds

    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const progressValue = Math.min((elapsed / duration) * 100, 100);
      setProgress(progressValue);

      if (progressValue >= 100) {
        clearInterval(interval);
        // Small delay before hiding
        setTimeout(onComplete, 300);
      }
    }, 16);

    return () => clearInterval(interval);
  }, [onComplete]);

  // Calculate dynamic spin duration - starts fast, gradually slows down
  const getSpinDuration = () => {
    if (progress < 30) return '0.3s';      // Very fast at start
    if (progress < 60) return '0.6s';      // Medium fast
    if (progress < 85) return '1.2s';      // Slowing down
    return '2.5s';                          // Slow at end
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-background transition-opacity duration-500">
      <div className="text-center">
        {/* Spinning Logo Container */}
        <div className="relative mx-auto h-32 w-32 sm:h-48 sm:w-48">
          {/* Outer spinning ring */}
          <div 
            className="absolute inset-0 animate-spin"
            style={{ animationDuration: getSpinDuration() }}
          >
            <div className="absolute inset-0 rounded-full border-4 border-[#839705] border-t-transparent" />
          </div>

          {/* Middle spinning ring (counter-rotating) */}
          <div 
            className="absolute inset-2 animate-spin"
            style={{ 
              animationDuration: getSpinDuration(),
              animationDirection: 'reverse'
            }}
          >
            <div className="absolute inset-0 rounded-full border-4 border-[#839705]/50 border-b-transparent" />
          </div>

          {/* Inner spinning ring */}
          <div 
            className="absolute inset-4 animate-spin"
            style={{ animationDuration: getSpinDuration() }}
          >
            <div className="absolute inset-0 rounded-full border-4 border-[#839705]/30 border-l-transparent" />
          </div>

          {/* Center Logo */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="relative h-16 w-16 sm:h-24 sm:w-24 animate-pulse">
              <img
                src={theme === "dark" ? "/dark-logo.svg" : "/light-logo.svg"}
                alt="Untangled IT Solutions"
                className="h-full w-full object-contain"
              />
            </div>
          </div>

          {/* Progress ring dots */}
          <div className="absolute -bottom-6 left-1/2 flex -translate-x-1/2 gap-1.5">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className={`h-2 w-2 rounded-full transition-all duration-300 ${
                  progress / 20 > i
                    ? 'bg-[#839705] scale-100'
                    : 'bg-[#839705]/20 scale-75'
                }`}
              />
            ))}
          </div>
        </div>

        {/* Loading Text */}
        <div className="mt-8 space-y-1">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[#839705]">
            Loading
          </p>
          <div className="mx-auto h-0.5 w-32 overflow-hidden rounded-full bg-[#839705]/20">
            <div
              className="h-full rounded-full bg-[#839705] transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {Math.round(progress)}%
          </p>
          <p className="text-[10px] text-muted-foreground/60 mt-1">
            {progress < 30 && '⚡ Initializing...'}
            {progress >= 30 && progress < 60 && '🔧 Loading components...'}
            {progress >= 60 && progress < 85 && '🚀 Preparing your experience...'}
            {progress >= 85 && progress < 100 && '✨ Almost there...'}
            {progress >= 100 && '✅ Ready!'}
          </p>
        </div>
      </div>
    </div>
  );
}