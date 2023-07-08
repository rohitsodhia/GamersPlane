import { agency_fb } from "@/app/util";
import classNames from "classnames";
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
    const classes = classNames(
        `headerbar text-white ${agency_fb.className}`,
        className
    );
    const el = createElement(
        level,
        {
            className: classes,
        },
        children
    );
    return el;
}
