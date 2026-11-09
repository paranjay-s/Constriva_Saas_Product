import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevated?: boolean;
  interactive?: boolean;
  selected?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  elevated = false,
  interactive = false,
  selected = false,
  className = '',
  ...props
}) => {
  const bg = elevated ? 'bg-[#2A2A2A]' : 'bg-[#202020]';
  const border = selected
    ? 'border-[#C5A77B] ring-1 ring-[#C5A77B]'
    : 'border-[#303030] hover:border-[#444444]';
  const interactiveStyles = interactive
    ? 'cursor-pointer transition-all duration-150 hover:-translate-y-0.5'
    : '';

  return (
    <div
      className={`rounded-lg border ${bg} ${border} ${interactiveStyles} p-6 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

