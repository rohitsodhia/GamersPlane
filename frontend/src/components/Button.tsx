import { agency_fb } from "@/app/util";
import clsx from "clsx";
import { ButtonHTMLAttributes, ReactNode } from "react";

type Props = {
    children: ReactNode;
    className?: string | string[];
} & ButtonHTMLAttributes<HTMLButtonElement>;

export default function Button(props: Props) {
    let { children, className = "", ...buttonProps } = props;
    const classes = clsx(
        `trapezoid bg-gp-red text-white ${agency_fb.className}`,
        className
    );
    return (
        <button {...buttonProps} className={classes}>
            <div className="px-2 py-1">{children}</div>
        </button>
    );
}
