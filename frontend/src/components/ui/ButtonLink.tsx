'use client';

import Link from 'next/link';
import type { AnchorHTMLAttributes, ReactNode } from 'react';

import { ButtonSize, ButtonVariant, buttonClassName } from './Button';

interface ButtonLinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'className' | 'href'> {
  href: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

function ButtonLinkContent({
  children,
  leftIcon,
  rightIcon,
}: Pick<ButtonLinkProps, 'children' | 'leftIcon' | 'rightIcon'>) {
  return (
    <>
      {leftIcon ? <span className="relative z-10 inline-flex items-center shrink-0">{leftIcon}</span> : null}
      <span className="relative z-10 inline-flex items-center gap-2 whitespace-nowrap [&>svg]:inline-block [&>svg]:shrink-0">
        {children}
      </span>
      {rightIcon ? <span className="relative z-10 inline-flex items-center shrink-0">{rightIcon}</span> : null}
    </>
  );
}

export function ButtonLink({
  href,
  variant = 'primary',
  size = 'md',
  className = '',
  leftIcon,
  rightIcon,
  children,
  target,
  rel,
  ...props
}: ButtonLinkProps) {
  const resolvedRel = target === '_blank' ? rel ?? 'noopener noreferrer' : rel;
  const classes = buttonClassName({ variant, size, className });

  if (target === '_blank') {
    return (
      <a href={href} target={target} rel={resolvedRel} className={classes} {...props}>
        <ButtonLinkContent leftIcon={leftIcon} rightIcon={rightIcon}>{children}</ButtonLinkContent>
      </a>
    );
  }

  return (
    <Link href={href} target={target} rel={resolvedRel} className={classes} {...props}>
      <ButtonLinkContent leftIcon={leftIcon} rightIcon={rightIcon}>{children}</ButtonLinkContent>
    </Link>
  );
}
