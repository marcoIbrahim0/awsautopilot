"use client"

import {
  forwardRef,
  useCallback,
  useEffect,
  useRef,
  useState,
  type MouseEvent,
} from "react"
import Image, { type StaticImageData } from "next/image"
import clsx from "clsx"
import {
  AnimatePresence,
  motion,
  useMotionTemplate,
  useMotionValue,
  type MotionStyle,
  type MotionValue,
  type Variants,
} from "motion/react"
import { cn } from "@/lib/utils"

// Types
type WrapperStyle = MotionStyle & {
  "--x": MotionValue<string>
  "--y": MotionValue<string>
}

interface CardProps {
  title?: string
  description?: string
  bgClass?: string
  className?: string
  cardStyle?: React.CSSProperties
}

interface ImageSet {
  step1dark1?: StaticImageData | string
  step1dark2?: StaticImageData | string
  step1light1: StaticImageData | string
  step1light2?: StaticImageData | string
  step2dark1?: StaticImageData | string
  step2dark2?: StaticImageData | string
  step2light1: StaticImageData | string
  step2light2?: StaticImageData | string
  step3dark?: StaticImageData | string
  step3light: StaticImageData | string
  step4light: StaticImageData | string
  alt: string
}

export interface FeatureCarouselStep {
  id: string
  name: string
  title: string
  description: string
}

interface FeatureCarouselProps extends CardProps {
  steps?: FeatureCarouselStep[]
  interval?: number
  step1img1Class?: string
  step1img2Class?: string
  step2img1Class?: string
  step2img2Class?: string
  step3imgClass?: string
  step4imgClass?: string
  image: ImageSet
}

interface StepImageProps {
  src: StaticImageData | string
  alt: string
  className?: string
  style?: React.CSSProperties
  width?: number
  height?: number
}

// Constants
const DEFAULT_STEPS: FeatureCarouselStep[] = [
  {
    id: "1",
    name: "Step 1",
    title: "Feature 1",
    description: "Feature 1 description",
  },
  {
    id: "2",
    name: "Step 2",
    title: "Feature 2",
    description: "Feature 2 description",
  },
  {
    id: "3",
    name: "Step 3",
    title: "Feature 3",
    description: "Feature 3 description",
  },
  {
    id: "4",
    name: "Step 4",
    title: "Feature 4",
    description: "Feature 4 description",
  },
]

/**
 * Animation presets for reusable motion configurations.
 * Each preset defines the initial, animate, and exit states,
 * along with spring physics parameters for smooth transitions.
 */
const ANIMATION_PRESETS = {
  fadeInScale: {
    initial: { opacity: 0, scale: 0.95 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.95 },
    transition: {
      type: "spring",
      stiffness: 300, // Higher value = more rigid spring
      damping: 25, // Higher value = less oscillation
      mass: 0.5, // Lower value = faster movement
    },
  },
  slideInRight: {
    initial: { opacity: 0, x: 20 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -20 },
    transition: {
      type: "spring",
      stiffness: 300,
      damping: 25,
      mass: 0.5,
    },
  },
  slideInLeft: {
    initial: { opacity: 0, x: -20 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: 20 },
    transition: {
      type: "spring",
      stiffness: 300,
      damping: 25,
      mass: 0.5,
    },
  },
} as const

type AnimationPreset = keyof typeof ANIMATION_PRESETS

interface AnimatedStepImageProps extends StepImageProps {
  preset?: AnimationPreset
  delay?: number
  onAnimationComplete?: () => void
}

/**
 * Custom hook for managing cyclic transitions with auto-play functionality.
 * Handles both automatic cycling and manual transitions between steps.
 */
function useNumberCycler(
  totalSteps: number,
  interval: number
) {
  const [currentNumber, setCurrentNumber] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Setup timer function
  const setupTimer = useCallback(() => {
    // Clear any existing timer
    if (timerRef.current) {
      clearInterval(timerRef.current)
    }

    if (totalSteps <= 1) return

    timerRef.current = setInterval(() => {
      setCurrentNumber((prev) => (prev + 1) % totalSteps)
    }, interval)
  }, [interval, totalSteps])

  // Handle manual increment
  const increment = useCallback(() => {
    setCurrentNumber((prev) => (prev + 1) % totalSteps)

    // Reset timer on manual interaction
    setupTimer()
  }, [totalSteps, setupTimer])

  // Initial timer setup and cleanup
  useEffect(() => {
    setupTimer()

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [setupTimer])

  return {
    currentNumber,
    increment,
    setCurrentNumber,
    resetTimer: setupTimer,
  }
}

function useIsMobile() {
  const [isMobile] = useState(() => {
    if (typeof window === "undefined") return false
    const userAgent = navigator.userAgent
    const isSmall = window.matchMedia("(max-width: 768px)").matches
    const isMobileDevice = Boolean(
      /Android|BlackBerry|iPhone|iPad|iPod|Opera Mini|IEMobile|WPDesktop/i.exec(
        userAgent
      )
    )

    const isDev = process.env.NODE_ENV !== "production"
    return isDev ? isSmall || isMobileDevice : isSmall && isMobileDevice
  })

  return isMobile
}

// Components
function IconCheck({ className, ...props }: React.ComponentProps<"svg">) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 256 256"
      fill="currentColor"
      className={cn("h-4 w-4", className)}
      {...props}
    >
      <path d="m229.66 77.66-128 128a8 8 0 0 1-11.32 0l-56-56a8 8 0 0 1 11.32-11.32L96 188.69 218.34 66.34a8 8 0 0 1 11.32 11.32Z" />
    </svg>
  )
}

const stepVariants: Variants = {
  inactive: {
    scale: 0.8,
    opacity: 0.5,
  },
  active: {
    scale: 1,
    opacity: 1,
  },
}

const StepImage = forwardRef<HTMLImageElement, StepImageProps>(
  (
    { src, alt, className, style, width = 1200, height = 630, ...props },
    ref
  ) => {
    return (
      <Image
        ref={ref}
        alt={alt}
        className={className}
        src={src}
        width={width}
        height={height}
        style={{
          position: "absolute",
          userSelect: "none",
          maxWidth: "unset",
          ...style,
        }}
        {...props}
      />
    )
  }
)
StepImage.displayName = "StepImage"

const MotionStepImage = motion(StepImage)

/**
 * Wrapper component for StepImage that applies animation presets.
 * Simplifies the application of complex animations through preset configurations.
 */
const AnimatedStepImage = ({
  preset = "fadeInScale",
  delay = 0,
  onAnimationComplete,
  ...props
}: AnimatedStepImageProps) => {
  const presetConfig = ANIMATION_PRESETS[preset]
  return (
    <MotionStepImage
      {...props}
      {...presetConfig}
      transition={{
        ...presetConfig.transition,
        delay,
      }}
      onAnimationComplete={onAnimationComplete}
    />
  )
}

/**
 * Main card component that handles mouse tracking for gradient effect.
 * Uses motion values to create an interactive gradient that follows the cursor.
 */
function FeatureCard({
  bgClass,
  children,
  className,
  cardStyle,
  step,
  steps,
}: CardProps & {
  children: React.ReactNode
  step: number
  steps: readonly FeatureCarouselStep[]
}) {
  const [mounted, setMounted] = useState(false)
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)
  const isMobile = useIsMobile()

  function handleMouseMove({ currentTarget, clientX, clientY }: MouseEvent) {
    if (isMobile) return
    const { left, top } = currentTarget.getBoundingClientRect()
    mouseX.set(clientX - left)
    mouseY.set(clientY - top)
  }

  useEffect(() => {
    setMounted(true)
  }, [])

  return (
    <motion.div
      className={cn("animated-cards relative w-full rounded-[16px]", className)}
      onMouseMove={handleMouseMove}
      style={
        {
          "--x": useMotionTemplate`${mouseX}px`,
          "--y": useMotionTemplate`${mouseY}px`,
        } as WrapperStyle
      }
    >
      <div
        className={clsx(
          "group relative w-full overflow-hidden rounded-3xl bg-[var(--surface-alt)] border border-[var(--border)] transition duration-300",
          "md:hover:border-[var(--accent)]",
          bgClass
        )}
        style={cardStyle}
      >
        <div className="m-6 min-h-[360px] sm:m-10 sm:min-h-[450px]">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              className="flex w-full flex-col gap-3 sm:w-4/6"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{
                duration: 0.3,
                ease: [0.23, 1, 0.32, 1],
              }}
            >
              <motion.h2
                className="text-xl font-bold tracking-tight text-white md:text-2xl"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{
                  delay: 0.1,
                  duration: 0.3,
                  ease: [0.23, 1, 0.32, 1],
                }}
              >
                {steps[step]?.title ?? ""}
              </motion.h2>
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{
                  delay: 0.2,
                  duration: 0.3,
                  ease: [0.23, 1, 0.32, 1],
                }}
              >
                <p className="text-sm leading-5 text-[var(--text-body)] sm:text-base sm:leading-5">
                  {steps[step]?.description ?? ""}
                </p>
              </motion.div>
            </motion.div>
          </AnimatePresence>
          {mounted ? children : null}
        </div>
      </div>
    </motion.div>
  )
}

/**
 * Progress indicator component that shows current step and completion status.
 * Handles complex state transitions and animations for step indicators.
 */
function Steps({
  steps,
  current,
  onChange,
}: {
  steps: readonly FeatureCarouselStep[]
  current: number
  onChange: (index: number) => void
}) {
  return (
    <nav aria-label="Progress" className="w-full px-2 sm:px-4">
      <div className="flex w-full justify-center">
        <ol
          className="flex w-max flex-nowrap items-center justify-center gap-1.5 py-0.5 sm:w-max sm:gap-2 md:mx-auto md:w-10/12 md:divide-y-0"
          role="list"
        >
          {steps.map((step, stepIdx) => {
            // Calculate step states for styling and animations
            const isCompleted = current > stepIdx
            const isCurrent = current === stepIdx
            const isFuture = !isCompleted && !isCurrent

            return (
              <motion.li
                key={`${step.name}-${stepIdx}`}
                initial="inactive"
                animate={isCurrent ? "active" : "inactive"}
                variants={stepVariants}
                transition={{ duration: 0.3 }}
                className={cn(
                  "relative z-50 shrink-0 rounded-full px-2 py-1 transition-all duration-300 ease-in-out sm:px-3 md:flex",
                  isCompleted ? "bg-neutral-500/20" : "bg-neutral-500/10"
                )}
              >
                <div
                  className={cn(
                    "group flex cursor-pointer items-center justify-center focus:outline-none focus-visible:ring-2",
                    (isFuture || isCurrent) && "pointer-events-none"
                  )}
                  onClick={() => onChange(stepIdx)}
                >
                  <span className="flex items-center gap-1.5 text-sm font-medium sm:gap-2">
                    <motion.span
                      initial={false}
                      animate={{
                        scale: isCurrent ? 1.2 : 1,
                      }}
                      className={cn(
                        "flex h-3 w-3 shrink-0 items-center justify-center rounded-full duration-300 sm:h-4 sm:w-4",
                        isCompleted &&
                        "bg-brand-400 text-white dark:bg-brand-400",
                        isCurrent &&
                        "bg-brand-300/80 text-neutral-400 dark:bg-neutral-500/50",
                        isFuture && "bg-brand-300/10 dark:bg-neutral-500/20"
                      )}
                    >
                      {isCompleted ? (
                        <motion.div
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{
                            type: "spring",
                            stiffness: 300,
                            damping: 20,
                          }}
                        >
                          <IconCheck className="h-3 w-3 stroke-white stroke-[3] text-white dark:stroke-black" />
                        </motion.div>
                      ) : (
                        <span
                          className={cn(
                            "text-[10px] sm:text-xs",
                            !isCurrent && "text-[var(--accent)]"
                          )}
                        >
                          {stepIdx + 1}
                        </span>
                      )}
                    </motion.span>
                    <motion.span
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      className={clsx(
                        "whitespace-nowrap text-[10px] font-medium leading-none duration-300 sm:text-sm",
                        isCompleted && "text-muted-foreground",
                        isCurrent && "text-[var(--accent)]",
                        isFuture && "text-neutral-500"
                      )}
                    >
                      {step.name}
                    </motion.span>
                  </span>
                </div>
              </motion.li>
            )
          })}
        </ol>
      </div>
    </nav>
  )
}

const defaultClasses = {
  step1img1:
    "pointer-events-none w-[50%] border border-border-100/10 transition-all duration-500 dark:border-border-700/50 rounded-2xl",
  step1img2:
    "pointer-events-none w-[60%] border border-border-100/10 dark:border-border-700/50 transition-all duration-500 overflow-hidden rounded-2xl",
  step2img1:
    "pointer-events-none w-[50%] border border-border-100/10 transition-all duration-500 dark:border-border-700 rounded-2xl overflow-hidden",
  step2img2:
    "pointer-events-none w-[40%] border border-border-100/10 dark:border-border-700 transition-all duration-500 rounded-2xl overflow-hidden",
  step3img:
    "pointer-events-none w-[90%] border border-border-100/10 dark:border-border-700 rounded-2xl transition-all duration-500 overflow-hidden",
  step4img:
    "pointer-events-none w-[90%] border border-border-100/10 dark:border-border-700 rounded-2xl transition-all duration-500 overflow-hidden",
} as const

/**
 * Main component that orchestrates the multi-step animation sequence.
 * Manages state transitions, handles animation timing, and prevents
 * animation conflicts through the isAnimating flag.
 */
export function FeatureCarousel({
  image,
  steps = DEFAULT_STEPS,
  interval = 3500,
  step1img1Class = defaultClasses.step1img1,
  step1img2Class = defaultClasses.step1img2,
  step2img1Class = defaultClasses.step2img1,
  step2img2Class = defaultClasses.step2img2,
  step3imgClass = defaultClasses.step3img,
  step4imgClass = defaultClasses.step4img,
  ...props
}: FeatureCarouselProps) {
  const safeSteps = steps.length > 0 ? steps : DEFAULT_STEPS
  const { currentNumber: step, increment, setCurrentNumber, resetTimer } =
    useNumberCycler(safeSteps.length, interval)
  const [isAnimating, setIsAnimating] = useState(false)

  const handleIncrement = () => {
    if (isAnimating) return
    setIsAnimating(true)
    increment()
  }

  const handleAnimationComplete = () => {
    setIsAnimating(false)
  }

  const renderStepContent = () => {
    const content = () => {
      switch (step) {
        case 0:
          /**
           * Layout: Two images side by side
           * - Left image (step1img1): 50% width, positioned left
           * - Right image (step1img2): 60% width, positioned right
           * Animation:
           * - Left image slides in from left
           * - Right image slides in from right with 0.1s delay
           * - Both use spring animation for smooth motion
           */
          return (
            <motion.div
              className="relative w-full h-full"
              onAnimationComplete={handleAnimationComplete}
            >
              {image.step1light1 ? (
                <AnimatedStepImage
                  alt={image.alt}
                  className={clsx(step1img1Class)}
                  src={image.step1light1}
                  preset="slideInLeft"
                />
              ) : null}
              {image.step1light2 ? (
                <AnimatedStepImage
                  alt={image.alt}
                  className={clsx(step1img2Class)}
                  src={image.step1light2}
                  preset="slideInRight"
                  delay={0.1}
                />
              ) : null}
            </motion.div>
          )
        case 1:
          /**
           * Layout: Two images with overlapping composition
           * - First image (step2img1): 50% width, positioned left
           * - Second image (step2img2): 40% width, overlaps first image
           * Animation:
           * - Both images fade in and scale up from 95%
           * - Second image has 0.1s delay for staggered effect
           * - Uses spring physics for natural motion
           */
          return (
            <motion.div
              className="relative w-full h-full"
              onAnimationComplete={handleAnimationComplete}
            >
              {image.step2light1 ? (
                <AnimatedStepImage
                  alt={image.alt}
                  className={clsx(step2img1Class, "rounded-2xl")}
                  src={image.step2light1}
                  preset="fadeInScale"
                />
              ) : null}
              {image.step2light2 ? (
                <AnimatedStepImage
                  alt={image.alt}
                  className={clsx(step2img2Class, "rounded-2xl")}
                  src={image.step2light2}
                  preset="fadeInScale"
                  delay={0.1}
                />
              ) : null}
            </motion.div>
          )
        case 2:
          /**
           * Layout: Single centered image
           * - Full width image (step3img): 90% width, centered
           * Animation:
           * - Fades in and scales up from 95%
           * - Uses spring animation for smooth scaling
           * - Triggers animation complete callback
           */
          return (
            <AnimatedStepImage
              alt={image.alt}
              className={clsx(step3imgClass, "rounded-2xl")}
              src={image.step3light}
              preset="fadeInScale"
              onAnimationComplete={handleAnimationComplete}
            />
          )
        case 3:
          /**
           * Layout: Single centered image
           * - Full-area container matches the other steps
           * Animation:
           * - Image fades in and scales up
           * - Uses spring physics for natural motion
           */
          return (
            <motion.div
              className="relative h-full w-full"
              onAnimationComplete={handleAnimationComplete}
            >
              <AnimatedStepImage
                alt={image.alt}
                className={clsx(step4imgClass, "rounded-2xl")}
                src={image.step4light}
                preset="fadeInScale"
                delay={0.05}
              />
            </motion.div>
          )
        default:
          return null
      }
    }

    return (
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          {...ANIMATION_PRESETS.fadeInScale}
          className="absolute inset-0 h-full w-full"
        >
          {content()}
        </motion.div>
      </AnimatePresence>
    )
  }

  return (
    <FeatureCard {...props} step={step} steps={safeSteps}>
      {renderStepContent()}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="relative z-50 mt-5 w-full md:absolute md:left-1/2 md:top-6 md:mt-0 md:h-full md:w-[min(520px,calc(100%-3rem))] md:-translate-x-1/2 lg:top-5"
      >
        <Steps
          current={step}
          onChange={(index) => {
            if (index === step || safeSteps.length <= 1) return
            setIsAnimating(true)
            setCurrentNumber(index)
            resetTimer()
          }}
          steps={safeSteps}
        />
      </motion.div>
      <motion.div
        className="absolute right-0 top-0 z-50 h-full w-full cursor-pointer md:left-0"
        onClick={handleIncrement}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      />
    </FeatureCard>
  )
}

export default FeatureCarousel
