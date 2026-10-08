"use client";

import React from "react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
}

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  children,
  ...props
}: ButtonProps) {
  const base = "inline-flex items-center justify-center font-medium rounded-panel transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-uv disabled:opacity-50 disabled:cursor-not-allowed";

  const sizeClasses = {
    sm: "px-2.5 py-1 text-xs",
    md: "px-3.5 py-1.5 text-xs",
    lg: "px-4 py-2 text-sm",
  }[size];

  const variantClasses = {
    primary: "bg-ink text-bg-raised hover:opacity-90 shadow-sm",
    secondary: "bg-bg-raised text-ink border border-line hover:bg-bg-sunken",
    danger: "bg-seal text-bg-raised hover:opacity-90",
    ghost: "text-ink-muted hover:text-ink hover:bg-bg-sunken/80",
  }[variant];

  return (
    <button className={`${base} ${sizeClasses} ${variantClasses} ${className}`} {...props}>
      {children}
    </button>
  );
}
export default Button;
