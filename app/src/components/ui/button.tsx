import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
    "inline-flex items-center justify-center whitespace-nowrap text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 uppercase tracking-wider font-mono active:scale-[0.98] relative overflow-hidden",
    {
        variants: {
            variant: {
                default: "bg-black text-white border border-white/20 group hover:border-transparent transition-colors z-10 before:absolute before:inset-0 before:bg-primary before:translate-x-[-100%] hover:before:translate-x-0 before:transition-transform before:duration-300 before:ease-out before:-z-10",
                destructive:
                    "bg-black text-white border border-white/20 group hover:border-transparent transition-colors z-10 before:absolute before:inset-0 before:bg-red-600 before:translate-x-[-100%] hover:before:translate-x-0 before:transition-transform before:duration-300 before:ease-out before:-z-10",
                outline:
                    "border border-input bg-background hover:bg-accent hover:text-accent-foreground hover:border-primary/50",
                secondary:
                    "bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-transparent hover:border-secondary-foreground/20",
                ghost: "hover:bg-accent hover:text-accent-foreground",
                link: "text-primary underline-offset-4 hover:underline lowercase tracking-normal font-sans normal-case",
                premium: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-[0_0_20px_rgba(99,102,241,0.3)] border border-primary/50 relative overflow-hidden group",
                tech: "bg-transparent border border-primary text-primary hover:bg-primary/10 hover:shadow-[0_0_15px_rgba(99,102,241,0.3)]",
                render: "bg-black text-white border border-white/20 group hover:border-transparent transition-colors z-10 before:absolute before:inset-0 before:bg-blue-600 before:translate-x-[-100%] hover:before:translate-x-0 before:transition-transform before:duration-300 before:ease-out before:-z-10",
                "render-red": "bg-black text-white border border-white/20 group hover:border-transparent transition-colors z-10 before:absolute before:inset-0 before:bg-red-600 before:translate-x-[-100%] hover:before:translate-x-0 before:transition-transform before:duration-300 before:ease-out before:-z-10",
                "render-purple": "bg-black text-white border border-white/20 group hover:border-transparent transition-colors z-10 before:absolute before:inset-0 before:bg-primary before:translate-x-[-100%] hover:before:translate-x-0 before:transition-transform before:duration-300 before:ease-out before:-z-10",
                "render-white": "bg-transparent text-black border border-white/20 hover:text-white group hover:border-transparent transition-colors z-10 overflow-hidden relative before:absolute before:inset-0 before:bg-primary before:translate-x-[-100%] hover:before:translate-x-0 before:transition-transform before:duration-300 before:ease-out before:-z-10 after:absolute after:inset-0 after:bg-white after:-z-20",
                "render-destructive": "bg-red-950/50 text-red-200 border border-red-900/50 hover:bg-transparent hover:text-white group hover:border-transparent transition-colors z-10 before:absolute before:inset-0 before:bg-red-600 before:translate-x-[-100%] hover:before:translate-x-0 before:transition-transform before:duration-300 before:ease-out before:-z-10",
                "render-success": "bg-transparent text-black border border-white/20 hover:text-white group hover:border-transparent transition-colors z-10 overflow-hidden relative before:absolute before:inset-0 before:bg-emerald-600 before:translate-x-[-100%] hover:before:translate-x-0 before:transition-transform before:duration-300 before:ease-out before:-z-10 after:absolute after:inset-0 after:bg-white after:-z-20",
            },
            size: {
                default: "h-10 px-6 py-2",
                sm: "h-8 px-3 text-xs",
                lg: "h-14 px-8 text-base",
                icon: "h-10 w-10",
            },
        },
        defaultVariants: {
            variant: "default",
            size: "default",
        },
    }
)

export interface ButtonProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
    asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant, size, asChild = false, ...props }, ref) => {
        const Comp = asChild ? Slot : "button"
        return (
            <Comp
                className={cn(buttonVariants({ variant, size, className }))}
                ref={ref}
                {...props}
            />
        )
    }
)
Button.displayName = "Button"

export { Button, buttonVariants }
