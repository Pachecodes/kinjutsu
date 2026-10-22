import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import { forwardRef, type ButtonHTMLAttributes } from 'react'

import { cn } from '../../lib/cn'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl font-semibold transition-colors ' +
    'disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary: 'bg-accent text-accent-ink hover:bg-accent/90 active:bg-accent/80',
        /** The one generation action. Depth comes from an olive base, not a glow. */
        cta:
          'bg-cta font-bold text-accent-ink shadow-[inset_0_-3px_0_hsl(var(--cta-base)/0.55)] hover:bg-cta-hover ' +
          'disabled:bg-ink-700 disabled:text-faint disabled:opacity-100 disabled:shadow-none',
        solid: 'bg-ink-700 text-fg hover:bg-ink-600',
        outline: 'border border-white/10 bg-white/[0.03] text-fg hover:bg-white/[0.08]',
        ghost: 'bg-transparent text-muted hover:bg-white/[0.06] hover:text-fg',
        danger: 'bg-danger/15 text-danger border border-danger/40 hover:bg-danger/25',
        link: 'text-accent underline-offset-4 hover:underline',
      },
      size: {
        sm: 'h-9 px-3 text-xs [&_svg]:size-3.5',
        md: 'h-10 px-3.5 text-sm [&_svg]:size-4',
        lg: 'h-12 px-5 text-sm [&_svg]:size-4',
        icon: 'size-10 [&_svg]:size-4',
        'icon-sm': 'size-8 rounded-lg [&_svg]:size-3.5',
      },
    },
    defaultVariants: { variant: 'solid', size: 'md' },
  },
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, asChild, loading, children, disabled, type = 'button', ...props },
  ref,
) {
  const Comp = asChild ? Slot : 'button'
  return (
    <Comp
      ref={ref}
      type={asChild ? undefined : type}
      disabled={disabled || loading}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    >
      {loading ? (
        <>
          <Loader2 className="animate-spin" aria-hidden />
          {children}
        </>
      ) : (
        children
      )}
    </Comp>
  )
})

export { buttonVariants }
