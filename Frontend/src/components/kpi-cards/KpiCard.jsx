import { motion } from "framer-motion";

export function KpiCard({ title, value, change, changeType = "up", icon: Icon, insight }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      className="w-full h-36 overflow-hidden rounded-xl bg-[#151619] p-4 card-shadow transition-shadow hover:card-shadow-hover cursor-pointer flex flex-col"
    >
      <div className="flex items-start justify-between w-full gap-3">
        <div className="flex flex-col flex-1 min-w-0 space-y-1.5">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground truncate w-full">
            {title}
          </p>

          <p className="text-2xl font-bold text-gray-300 truncate w-full">
            {value}
          </p>

          {change && (
            <p
              className={`text-xs font-medium truncate w-full ${
                changeType === "up"
                  ? "text-success"
                  : changeType === "down"
                  ? "text-destructive"
                  : "text-muted-foreground"
              }`}
            >
              {change}
            </p>
          )}
        </div>

        {Icon && (
          <div className="shrink-0 flex items-center justify-center w-10 h-10 rounded-lg bg-white/10">
            <Icon className="h-5 w-5 opacity-70" />
          </div>
        )}
      </div>

      {insight && (
        <div className="mt-auto pt-3 border-t border-white/5 text-[11px] text-muted-foreground leading-relaxed line-clamp-2" title={insight}>
          {insight}
        </div>
      )}
    </motion.div>
  );
}
