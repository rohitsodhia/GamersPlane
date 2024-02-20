import { agency_fb } from "@/app/util";
import clsx from "clsx";
import { ReactNode, createElement } from "react";

type Props = {
    children?: ReactNode;
    className?: string | string[];
    level?: "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
};

export default function Headerbar({
    children,
    className = "",
    level = "h1",
}: Props) {
    const classes = clsx(
        `headerbar text-white ${agency_fb.className}`,
        className
    );
    const el = createElement(
        level,
        {
            className: classes,
        },
        <div className="px-2">{children}</div>
    );
    return el;
}
