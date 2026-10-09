import styles from "./-chat-point.module.css";

function ChatPoint({ className }: { className?: string }) {
	return (
		<svg
			xmlns="http://www.w3.org/2000/svg"
			width="16px"
			height="16px"
			viewBox="0 0 16 16"
			className={className}
		>
			<title>Chat bubble point</title>
			<polygon
				className={styles["outline"]}
				points="16,0.752 16,0 14,0 0,16 14,12 14,16 16,16 16,9.349 5.97,12.214 "
			/>
			<polygon className={styles["fill"]} points="16,9.346 5.971,12.211 16,0.75 " />
		</svg>
	);
}
export default ChatPoint;
