import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'accent' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  icon?: React.ReactNode;
  fullWidth?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  loading = false,
  leftIcon,
  rightIcon,
  icon,
  fullWidth = false,
  className = '',
  disabled,
  ...props
}) => {
  const effectiveLoading = isLoading || loading;
  const effectiveLeftIcon = leftIcon || icon;

  const baseStyles =
    'inline-flex items-center justify-center font-medium transition-all duration-150 rounded cursor-pointer select-none disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-1 focus:ring-[#C5A77B]';

  const sizeStyles = {
    sm: 'text-xs px-3 py-1.5 h-8 gap-1.5',
    md: 'text-sm px-4 py-2.5 h-11 gap-2',
    lg: 'text-base px-6 py-3 h-12 gap-2.5',
  };

  const variantStyles = {
    // Primary: Warm ivory with canvas dark text
    primary:
      'bg-[#F5F2EB] text-[#101010] hover:bg-[#EAE6DD] active:bg-[#DCD8CF] font-semibold tracking-tight shadow-sm',
    // Accent: Brand bronze with dark text
    accent:
      'bg-[#C5A77B] text-[#101010] hover:bg-[#D4B98E] active:bg-[#B39467] font-semibold tracking-tight',
    // Secondary: Dark panel with hairline border
    secondary:
      'bg-[#181818] border border-[#303030] text-[#FFFFFF] hover:bg-[#202020] hover:border-[#444444] active:bg-[#252525]',
    // Ghost: Transparent with border
    ghost:
      'bg-transparent text-[#A6A6A6] hover:text-[#FFFFFF] hover:bg-[#181818] active:bg-[#202020]',
    // Danger
    danger:
      'bg-[#93000A] text-[#FFDAD6] hover:bg-[#B31B22] active:bg-[#730007]',
  };

  return (
    <button
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${
        fullWidth ? 'w-full' : ''
      } ${className}`}
      disabled={disabled || effectiveLoading}
      {...props}
    >
      {effectiveLoading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        effectiveLeftIcon
      )}
      {children && <span>{children}</span>}
      {!effectiveLoading && rightIcon}
    </button>
  );
};
